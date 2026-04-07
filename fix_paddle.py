import re

path = r'c:\DoAn\hardware\ai_service\modules\plate_recognizer.py'
content = open(path, encoding='utf-8').read()

# ─── Replace 1: _load_models ─────────────────────────────────────────────
start = content.find('    def _load_models(self):')
end   = content.find('\n    # ─── Normalize', start)
if start == -1 or end == -1:
    print(f"FAIL load_models: start={start} end={end}")
    exit(1)

new_load = '''    def _load_models(self):
        # PaddleOCR (primary engine)
        self._paddle = None
        try:
            import os
            os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
            from paddleocr import PaddleOCR
            self._paddle = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
            logger.info("Plate OCR (PaddleOCR) da san sang")
        except Exception as e:
            logger.warning(f"PaddleOCR khong kha dung: {e}")

        # EasyOCR (fallback)
        self._ocr = None
        try:
            import easyocr
            self._ocr = easyocr.Reader(["en"], gpu=True, verbose=False)
            _blank = np.ones((64, 200, 3), np.uint8) * 255
            self._ocr.readtext(_blank, detail=0)
            logger.info("Plate OCR (EasyOCR) da san sang")
        except Exception as e:
            logger.error(f"Loi load EasyOCR: {e}")

        self._ready = (self._paddle is not None) or (self._ocr is not None)

        # doctr (last resort)
        self._doctr = None
        try:
            from doctr.models import ocr_predictor
            self._doctr = ocr_predictor(
                det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True
            )
            self._doctr([np.ones((64, 200, 3), np.uint8) * 255])
            logger.info("Plate OCR (doctr) da san sang")
        except Exception as e:
            logger.warning(f"doctr khong kha dung: {e}")
'''
content = content[:start] + new_load + content[end:]
print("load_models replaced OK")

# ─── Replace 2: _run_ocr + add _run_ocr_paddle ───────────────────────────
run_ocr_start = content.find('\n    def _run_ocr(')
run_ocr_end   = content.find('\n    def _run_ocr_doctr(', run_ocr_start)
if run_ocr_start == -1 or run_ocr_end == -1:
    print(f"FAIL run_ocr: start={run_ocr_start} end={run_ocr_end}")
    exit(1)

new_run_ocr = '''
    def _run_ocr(self, img):
        if self._ocr is None:
            return [], 0.0
        results = self._ocr.readtext(
            img,
            detail=1,
            paragraph=False,
            allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
            width_ths=0.4,
            contrast_ths=0.05,
            mag_ratio=1.5,
        )
        if not results:
            return [], 0.0
        results = sorted(results, key=lambda r: sum(pt[1] for pt in r[0]) / 4)
        conf    = float(np.mean([r[2] for r in results]))
        return results, conf

    def _run_ocr_paddle(self, img):
        """PaddleOCR -> (raw_text, confidence)"""
        if self._paddle is None:
            return "", 0.0
        try:
            import os
            os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
            bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img
            result = self._paddle.predict(bgr)
            all_boxes = []
            if result and isinstance(result, list):
                for page in result:
                    if not isinstance(page, dict):
                        continue
                    rec_texts  = page.get('rec_texts',  []) or []
                    rec_scores = page.get('rec_scores', []) or []
                    dt_polys   = page.get('dt_polys',   []) or []
                    for text, score, poly in zip(rec_texts, rec_scores, dt_polys):
                        if not text:
                            continue
                        ys = [p[1] for p in poly] if poly else [0]
                        xs = [p[0] for p in poly] if poly else [0]
                        cy = float(np.mean(ys))
                        cx = float(np.mean(xs))
                        all_boxes.append((cy, cx, text.upper(), float(score)))
            if not all_boxes:
                return "", 0.0
            all_boxes.sort(key=lambda w: (round(w[0] / 10) * 10, w[1]))
            # Group into rows by Y-gap
            rows = [[all_boxes[0]]]
            for box in all_boxes[1:]:
                if box[0] - rows[-1][-1][0] > 12:
                    rows.append([])
                rows[-1].append(box)
            merged = ""
            confs  = []
            for row in rows:
                row.sort(key=lambda w: w[1])
                merged += "".join(w[2] for w in row)
                confs.extend(w[3] for w in row)
            return merged, float(np.mean(confs)) if confs else 0.0
        except Exception as e:
            logger.warning(f"PaddleOCR loi: {e}")
            return "", 0.0

'''
content = content[:run_ocr_start] + new_run_ocr + content[run_ocr_end:]
print("_run_ocr + _run_ocr_paddle replaced OK")

# ─── Replace 3: recognize() – add PaddleOCR as step 1 ───────────────────
old_recognize_inner = '''        try:
            candidates = []

            # ── Buoc 1: Lay ROI bien so ──────────────────────────────────────
            roi = self._find_plate_roi(image)
            source = roi if roi is not None else image
            source_label = "ROI" if roi is not None else "FULL"

            # ── Buoc 2: Thu 3 bien the xu ly anh, EasyOCR ──────────────────
            # Tra ve ngay khi dat bien so hop le voi conf >= 0.65
            variants = self._preprocess_variants(source, is_roi=(roi is not None))
            for vi, variant in enumerate(variants):
                results, conf = self._run_ocr(variant)
                raw           = self._reconstruct_2line(results)
                plate         = self._normalize_plate(raw)'''

new_recognize_inner = '''        try:
            candidates = []

            # ── Buoc 1: Lay ROI bien so ──────────────────────────────────────
            roi = self._find_plate_roi(image)
            source = roi if roi is not None else image
            source_label = "ROI" if roi is not None else "FULL"

            # ── Buoc 2: PaddleOCR (primary) – thu tren V1 va V2 ─────────────
            if self._paddle is not None:
                for vi, variant in enumerate(self._preprocess_variants(source, is_roi=(roi is not None))[:2]):
                    raw_p, conf_p = self._run_ocr_paddle(variant)
                    plate_p       = self._normalize_plate(raw_p)
                    logger.info(f"[{source_label}/Paddle/V{vi+1}] raw='{raw_p}' -> plate='{plate_p}' conf={conf_p:.2f}")
                    if self._is_valid_plate(plate_p):
                        candidates.append((plate_p, conf_p))
                        if conf_p >= 0.75:
                            logger.info(f"[{source_label}/Paddle/V{vi+1}] Early exit conf={conf_p:.2f}")
                            break
                    else:
                        tokens = re.findall(r'[A-Z0-9]+', raw_p.upper())
                        for i in range(len(tokens)):
                            for j in range(i + 1, min(i + 4, len(tokens) + 1)):
                                p2 = self._normalize_plate("".join(tokens[i:j]))
                                if self._is_valid_plate(p2):
                                    candidates.append((p2, conf_p * 0.85))

            # ── Buoc 3: EasyOCR (fallback) – thu 3 bien the xu ly anh ───────
            # Chi chay neu PaddleOCR chua co ket qua hop le du tin
            top_conf = max((c for _, c in candidates), default=0.0)
            if top_conf < 0.75:
                variants = self._preprocess_variants(source, is_roi=(roi is not None))
                for vi, variant in enumerate(variants):
                    results, conf = self._run_ocr(variant)
                    raw           = self._reconstruct_2line(results)
                    plate         = self._normalize_plate(raw)'''

# Use find-based replacement for the whole try-block (more robust)
try_start = content.find('        try:\n            candidates = []')
try_end_marker = '        except Exception as e:\n            logger.error(f"Loi plate recognition: {e}", exc_info=True)'
try_end = content.find(try_end_marker, try_start)
if try_start == -1 or try_end == -1:
    print(f"FAIL try block: try_start={try_start} try_end={try_end}")
    idx = content.find('candidates = []')
    if idx != -1:
        print("candidates context:", repr(content[idx-30:idx+200]))
    exit(1)

new_try_block = '''        try:
            candidates = []

            # ── Buoc 1: Lay ROI bien so ──────────────────────────────────────
            roi = self._find_plate_roi(image)
            source = roi if roi is not None else image
            source_label = "ROI" if roi is not None else "FULL"

            # ── Buoc 2: PaddleOCR (engine chinh) ─────────────────────────────
            if self._paddle is not None:
                for vi, variant in enumerate(self._preprocess_variants(source, is_roi=(roi is not None))[:2]):
                    raw_p, conf_p = self._run_ocr_paddle(variant)
                    plate_p       = self._normalize_plate(raw_p)
                    logger.info(f"[{source_label}/Paddle/V{vi+1}] raw=\'{raw_p}\' -> plate=\'{plate_p}\' conf={conf_p:.2f}")
                    if self._is_valid_plate(plate_p):
                        candidates.append((plate_p, conf_p))
                        if conf_p >= 0.75:
                            logger.info(f"[{source_label}/Paddle/V{vi+1}] Early exit conf={conf_p:.2f}")
                            break
                    else:
                        tokens = re.findall(r\'[A-Z0-9]+\', raw_p.upper())
                        for i in range(len(tokens)):
                            for j in range(i + 1, min(i + 4, len(tokens) + 1)):
                                p2 = self._normalize_plate("".join(tokens[i:j]))
                                if self._is_valid_plate(p2):
                                    candidates.append((p2, conf_p * 0.85))

            # ── Buoc 3: EasyOCR (fallback) ───────────────────────────────────
            top_conf = max((c for _, c in candidates), default=0.0)
            if top_conf < 0.75:
                variants = self._preprocess_variants(source, is_roi=(roi is not None))
                for vi, variant in enumerate(variants):
                    results, conf = self._run_ocr(variant)
                    raw           = self._reconstruct_2line(results)
                    plate         = self._normalize_plate(raw)
                    logger.info(f"[{source_label}/EasyOCR/V{vi+1}] raw=\'{raw}\' -> plate=\'{plate}\' conf={conf:.2f}")
                    if self._is_valid_plate(plate):
                        candidates.append((plate, conf))
                        if conf >= 0.65:
                            logger.info(f"[{source_label}/EasyOCR/V{vi+1}] Early exit conf={conf:.2f}")
                            break
                    else:
                        tokens = re.findall(r\'[A-Z0-9]+\', raw.upper())
                        for i in range(len(tokens)):
                            for j in range(i + 1, min(i + 4, len(tokens) + 1)):
                                p2 = self._normalize_plate("".join(tokens[i:j]))
                                if self._is_valid_plate(p2):
                                    candidates.append((p2, conf * 0.85))

            # ── Buoc 4: Neu ROI that bai, thu toan frame ─────────────────────
            if not candidates and roi is not None:
                for vi, variant in enumerate(self._preprocess_variants(image, is_roi=False)):
                    results, conf = self._run_ocr(variant)
                    raw           = self._reconstruct_2line(results)
                    plate         = self._normalize_plate(raw)
                    logger.info(f"[FULL-FB/V{vi+1}] raw=\'{raw}\' -> plate=\'{plate}\' conf={conf:.2f}")
                    if self._is_valid_plate(plate):
                        candidates.append((plate, conf * 0.9))
                        if conf >= 0.65:
                            break
                    else:
                        tokens = re.findall(r\'[A-Z0-9]+\', raw.upper())
                        for i in range(len(tokens)):
                            for j in range(i + 1, min(i + 4, len(tokens) + 1)):
                                p2 = self._normalize_plate("".join(tokens[i:j]))
                                if self._is_valid_plate(p2):
                                    candidates.append((p2, conf * 0.75))

            # ── Buoc 5: doctr LAST RESORT ────────────────────────────────────
            if not candidates and self._doctr is not None:
                best_variant = self._preprocess_variants(source, is_roi=(roi is not None))[0]
                raw_d, conf_d = self._run_ocr_doctr(best_variant)
                plate_d = self._normalize_plate(raw_d)
                logger.info(f"[doctr] raw=\'{raw_d}\' -> plate=\'{plate_d}\' conf={conf_d:.2f}")
                if self._is_valid_plate(plate_d):
                    candidates.append((plate_d, conf_d))
                elif len(plate_d) >= 7:
                    candidates.append((plate_d, conf_d * 0.5))

            if not candidates:
                return {"plate": "", "confidence": 0.0, "roi_image": None, "ocr_raw": ""}

            best_plate, best_conf = max(candidates, key=lambda x: x[1])
            logger.info(f"[RESULT] plate=\'{best_plate}\' conf={best_conf:.2f}")
            return {
                "plate":      best_plate,
                "confidence": round(min(best_conf, 1.0), 4),
                "roi_image":  None,
                "ocr_raw":    best_plate,
            }
'''
content = content[:try_start] + new_try_block + '\n' + content[try_end:]
print("recognize() try-block replaced OK")

open(path, 'w', encoding='utf-8').write(content)
print("File written OK")
