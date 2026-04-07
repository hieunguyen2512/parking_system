"""Quick test: send a synthetic plate image to paddle_worker and check result."""
import os, sys, json, base64, subprocess, numpy as np, cv2, time

# Build a test plate image: "29Y3" on line 1, "03658" on line 2
img = np.ones((60, 170, 3), dtype='uint8') * 230
cv2.putText(img, '29Y3',  (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,0), 2)
cv2.putText(img, '03658', (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
b64 = base64.b64encode(buf.tobytes()).decode()
first_msg = json.dumps({'img': b64}) + '\n'

env = {
    **os.environ,
    'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK': 'True',
    'PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT': '0',
}
proc = subprocess.Popen(
    [sys.executable, os.path.join(os.path.dirname(__file__),
     'hardware', 'ai_service', 'modules', 'paddle_worker.py')],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=open('logs/paddle_worker_test_run.log', 'w'), text=True, bufsize=1, env=env)

print("Waiting for worker ready...")
t0 = time.time()
while time.time() - t0 < 90:
    line = proc.stdout.readline()
    if not line:
        break
    try:
        msg = json.loads(line)
    except Exception:
        continue
    if msg.get('status') == 'error':
        print('Worker init error:', msg)
        break
    if msg.get('status') == 'ready':
        print(f'Worker ready in {time.time()-t0:.1f}s, sending plate image...')
        proc.stdin.write(first_msg)
        proc.stdin.flush()
        resp_line = proc.stdout.readline()
        resp = json.loads(resp_line)
        print('PaddleOCR result:', resp)
        break
proc.terminate()
