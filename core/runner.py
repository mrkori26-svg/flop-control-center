import subprocess


def _background_subprocess_kwargs() -> dict[str, object]:
    """Keep console-capable helpers invisible when this stack runs unattended."""
    if __import__("sys").platform != "win32":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def run(cmd, cwd=None, timeout=12):
    try:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            **_background_subprocess_kwargs(),
        )
        return {'ok': p.returncode == 0, 'code': p.returncode, 'out': p.stdout.strip(), 'err': p.stderr.strip()}
    except Exception as exc:
        return {'ok': False, 'code': -1, 'out': '', 'err': str(exc)}
