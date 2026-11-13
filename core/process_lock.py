'''Process-held writer lock: operating system releases ownership after a crash.'''
import os
from contextlib import contextmanager
class WriterAlreadyRunning(RuntimeError):
    pass
@contextmanager
def writer_lock(path):
    # Keep the inode/path stable. Unlinking an advisory-lock file creates a race.
    fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600)
    held=False
    try:
        if os.fstat(fd).st_size==0:
            os.write(fd,b'\0')
        os.lseek(fd,0,os.SEEK_SET)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            held=True
        except OSError as exc:
            raise WriterAlreadyRunning('FLOP_STACK_STATE_WRITER_ALREADY_RUNNING') from exc
        yield
    finally:
        if held:
            os.lseek(fd,0,os.SEEK_SET)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
