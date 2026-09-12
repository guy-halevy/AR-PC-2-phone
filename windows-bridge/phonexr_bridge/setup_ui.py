"""Local companion launcher. Pairing secrets are displayed locally, never logged."""
import ipaddress
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading


def private_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
        return any(address in net for net in PRIVATE_NETWORKS)
    except ipaddress.AddressValueError:
        return False


PRIVATE_NETWORKS = tuple(ipaddress.IPv4Network(net) for net in
                         ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16'))


def addresses():
    try:
        found = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        return sorted({entry[4][0] for entry in found if private_ipv4(entry[4][0])})
    except OSError:
        return []


def bridge_command(host):
    if not private_ipv4(host):
        raise ValueError('Choose this PC’s private IPv4 address.')
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    command = [str(base/'PhoneXRBridge.exe')] if getattr(sys, 'frozen', False) else [sys.executable, str(base/'bridge.py')]
    return command + ['--host', host, '--gui-control']


def main(smoke_test=False):
    import tkinter as tk
    from tkinter import ttk, messagebox
    root = tk.Tk()
    root.title('PhoneXR Companion')
    root.geometry('640x440')
    root.minsize(540, 410)
    root.configure(padx=24, pady=20)
    events = queue.SimpleQueue()
    process = None
    closing = False
    pairing = ''
    copied = ''
    status = tk.StringVar(value='Start SteamVR, then open Desktop+ and connect your phone.')
    choices = addresses()
    host = tk.StringVar(value=choices[0] if choices else '')
    ttk.Label(root, text='PhoneXR', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
    ttk.Label(root, text='Connect your phone and control your desktop', padding=(0, 4, 0, 16)).pack(anchor='w')
    ttk.Label(root, text='This PC’s private IPv4 address').pack(anchor='w')
    selector = ttk.Combobox(root, textvariable=host, values=choices)
    selector.pack(fill='x', pady=(4, 12))
    row = ttk.Frame(root)
    row.pack(fill='x')
    secret = tk.StringVar()
    entry = ttk.Entry(root, textvariable=secret, state='readonly')
    ttk.Label(root, text='Pairing code — enter it in PhoneXR on your phone', padding=(0, 18, 0, 4)).pack(anchor='w')
    entry.pack(fill='x')

    def clear_secret():
        nonlocal pairing, copied
        pairing = ''
        secret.set('')
        try:
            if copied and root.clipboard_get() == copied:
                root.clipboard_clear()
        except tk.TclError:
            pass
        copied = ''

    def send(key):
        if process and process.poll() is None:
            try:
                process.stdin.write(key+'\n')
                process.stdin.flush()
            except (OSError, ValueError):
                status.set('Connection stopped. Input will be released.')

    def stop():
        send('q')
        clear_secret()
        enable.configure(state='disabled')
        disable.configure(state='disabled')
        status.set('Stopping and releasing input…')

    def read_output(child):
        try:
            for line in child.stdout:
                events.put((child, line.strip()))
        finally:
            child.wait()
            events.put((child, None))

    def start():
        nonlocal process
        if process and process.poll() is None:
            return
        try:
            process = subprocess.Popen(bridge_command(host.get().strip()), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, ValueError) as error:
            messagebox.showerror('Cannot start PhoneXR', str(error))
            return
        clear_secret()
        start_button.configure(state='disabled')
        selector.configure(state='disabled')
        status.set('Connecting… Input is disabled.')
        threading.Thread(target=read_output, args=(process,), daemon=True).start()

    def desktop():
        base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
        exe = base/'DesktopPlus'/'DesktopPlus.exe'
        if not exe.is_file():
            messagebox.showinfo('Desktop+ unavailable', 'Install the full PhoneXR companion package to include Desktop+.')
            return
        try:
            subprocess.Popen([str(exe)], cwd=exe.parent)
        except OSError as error:
            messagebox.showerror('Cannot open Desktop+', str(error))

    def copy():
        nonlocal copied
        if pairing:
            root.clipboard_clear()
            root.clipboard_append(pairing)
            copied = pairing
            status.set('Pairing code copied. Input remains under your control below.')

    ttk.Button(row, text='Open Desktop+', command=desktop).pack(side='left')
    start_button = ttk.Button(row, text='Start connection', command=start)
    start_button.pack(side='left', padx=8)
    ttk.Button(row, text='Stop', command=stop).pack(side='left')
    ttk.Button(root, text='Copy pairing code', command=copy).pack(anchor='w', pady=8)
    controls = ttk.Frame(root)
    controls.pack(fill='x', pady=8)
    enable = ttk.Button(controls, text='Enable hand input', command=lambda: send('e'), state='disabled')
    enable.pack(side='left')
    disable = ttk.Button(controls, text='Disable and release', command=lambda: send('d'), state='disabled')
    disable.pack(side='left', padx=8)
    ttk.Label(root, textvariable=status, wraplength=580).pack(anchor='w', pady=12)
    ttk.Label(root, text='Same private network • Pair again after restarting • Keep the pairing code private', wraplength=580).pack(anchor='w')

    def poll():
        nonlocal process, pairing
        while not events.empty():
            child, line = events.get()
            if child is not process:
                continue
            if line is None:
                code = child.returncode
                process = None
                clear_secret()
                enable.configure(state='disabled')
                disable.configure(state='disabled')
                start_button.configure(state='normal')
                selector.configure(state='normal')
                status.set('Stopped. Input disabled.' if code == 0 else 'Connection failed. Check the selected address and whether another companion is running.')
            elif line.startswith('phonexr://pair?data='):
                pairing = line
                secret.set(line)
                enable.configure(state='normal')
                disable.configure(state='normal')
                status.set('Connected. Pair your phone. Input DISABLED.')
            elif line in ('Input ENABLED', 'Input DISABLED'):
                status.set(line)
            elif 'did not accept contact release' in line:
                messagebox.showerror('Input release failed', 'Windows rejected contact release. Use your physical mouse or keyboard to recover the desktop.')
            # Other output (including exceptions) is intentionally not logged or displayed.
        if closing and process is None:
            root.destroy()
        else:
            root.after(50, poll)

    def close():
        nonlocal closing
        closing = True
        stop()
        # Keep pumping until the child acknowledges its release-and-exit path.

    root.protocol('WM_DELETE_WINDOW', close)
    root.after(50, poll)
    if smoke_test:
        root.after(100, root.destroy)
    root.mainloop()


if __name__ == '__main__':
    main()
