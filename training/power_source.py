"""Read macOS power state without recording hardware identifiers or changing settings."""
import platform
import re
import subprocess


class PowerUnavailable(RuntimeError):
    pass


def require_power(status, hardware="", *, clocked=False):
    if "drawing from 'AC Power'" not in status:
        raise PowerUnavailable("Mac is on battery")
    if "InternalBattery" not in status:
        return
    pct=re.search(r"(\d+)%",status)
    discharging="discharging" in status.lower()
    detached=bool(re.search(r'^\s*"ExternalConnected"\s*=\s*No\s*$',hardware,re.M))
    incapable=bool(re.search(r'^\s*"ExternalChargeCapable"\s*=\s*No\s*$',hardware,re.M))
    if discharging and (detached or incapable):
        raise PowerUnavailable("battery controller reports no charge-capable adapter while discharging")
    if clocked and (not pct or int(pct[1])<20 or discharging):
        raise PowerUnavailable("matches/training require non-discharging AC and at least 20%")
    if not clocked and discharging and (not pct or int(pct[1])<=25):
        raise PowerUnavailable("datagen low-battery guard")


def check(*,clocked=False):
    if platform.system()!="Darwin":
        return
    status=subprocess.check_output(["pmset","-g","batt"],text=True,timeout=5)
    hardware=""
    if "InternalBattery" in status and "discharging" in status.lower():
        hardware=subprocess.check_output(["ioreg","-rc","AppleSmartBattery","-w0"],text=True,timeout=5)
    require_power(status,hardware,clocked=clocked)
