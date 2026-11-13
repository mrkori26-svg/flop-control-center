import os,subprocess,sys,time
from pathlib import Path
from core.process_lock import writer_lock, WriterAlreadyRunning
def test_crashed_writer_releases_lock_and_active_writer_is_rejected(tmp_path):
 lock=tmp_path/'writer.lock'; ready=tmp_path/'ready'
 code="from core.process_lock import writer_lock;from pathlib import Path;import sys,time\nwith writer_lock(Path(sys.argv[1])):\n Path(sys.argv[2]).write_text('ready')\n time.sleep(30)\n"
 proc=subprocess.Popen([sys.executable,'-c',code,str(lock),str(ready)],cwd=Path(__file__).resolve().parents[1],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 try:
  for _ in range(100):
   if ready.exists():break
   if proc.poll() is not None:raise AssertionError('child failed')
   time.sleep(.02)
  assert ready.exists()
  try:
   with writer_lock(lock):raise AssertionError('concurrent writer accepted')
  except WriterAlreadyRunning:pass
 finally:proc.kill();proc.wait(timeout=5)
 with writer_lock(lock):assert lock.exists()
