#!/usr/bin/python3
"""PYRION OS - supervisor unico del escritorio y servicios graficos.

/init conserva la responsabilidad de boot.py, Xorg y la transicion visual.
Este supervisor arranca PYRION directamente y, dos segundos despues,
AMDEV, Floating Console y XTest. Reinicia componentes independientemente.
"""
import os
import signal
import subprocess
import time
from pathlib import Path

PYTHON = '/usr/bin/python3'
START_DELAY = 2.0
RETRY_DELAY = 3.0
RUNNING = True
CHILDREN = {
    'pyrion': ('/opt/pyrionos/app.py', '/var/log/pyrion-desktop.log'),
    'amdev': ('/opt/amdev/app.py', '/var/log/amdev.log'),
    'floating': ('/opt/minilinux/floating_console.py', '/var/log/floating-console.log'),
    'input_xtest': ('/opt/minilinux/input_xtest.py', '/var/log/input-xtest.log'),
}
PROCESSES = {}
NEXT_RETRY = {}


def stop(_signum, _frame):
    global RUNNING
    RUNNING = False


def start(name):
    path, logname = CHILDREN[name]
    if not Path(path).is_file():
        print(f'{name}: archivo inexistente: {path}', flush=True)
        return False

    env = os.environ.copy()
    env.setdefault('DISPLAY', ':0')
    env.setdefault('HOME', '/root')
    env['PYTHONUNBUFFERED'] = '1'
    if name in ('pyrion', 'amdev'):
        env['AMDEV_MODE'] = 'repo'

    Path(logname).parent.mkdir(parents=True, exist_ok=True)
    with open(logname, 'ab', buffering=0) as output:
        output.write(f'\n[{time.strftime("%Y-%m-%d %H:%M:%S")}] iniciar {name}: {path}\n'.encode())
        proc = subprocess.Popen(
            [PYTHON, path],
            cwd=str(Path(path).parent),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    PROCESSES[name] = proc
    print(f'{name}: iniciado PID {proc.pid}', flush=True)
    return True


def attempt_start(name, now):
    try:
        start(name)
    except OSError as exc:
        print(f'{name}: fallo de arranque: {exc}', flush=True)
    NEXT_RETRY[name] = now + RETRY_DELAY


def shutdown():
    for name, proc in list(PROCESSES.items()):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for name, proc in list(PROCESSES.items()):
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    PROCESSES.clear()


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGHUP, stop)
    start_time = time.monotonic()
    attempt_start('pyrion', start_time)
    deadline = start_time + START_DELAY
    additional_started = False
    try:
        while RUNNING:
            now = time.monotonic()
            if not additional_started and now >= deadline:
                additional_started = True
                for name in ('input_xtest', 'amdev', 'floating'):
                    attempt_start(name, now)

            for name in CHILDREN:
                if name != 'pyrion' and not additional_started:
                    continue
                proc = PROCESSES.get(name)
                if proc is not None and proc.poll() is not None:
                    print(f'{name}: terminó con código {proc.returncode}', flush=True)
                    PROCESSES.pop(name, None)
                    NEXT_RETRY[name] = now + RETRY_DELAY
                if name not in PROCESSES and now >= NEXT_RETRY.get(name, 0):
                    attempt_start(name, now)
            time.sleep(0.15)
    finally:
        shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

