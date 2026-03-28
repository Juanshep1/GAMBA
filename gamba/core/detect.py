"""Auto-detect local AI models and platform capabilities.

Scans the device for:
- Ollama models (localhost:11434)
- LM Studio (localhost:1234)
- LocalAI (localhost:8080)
- llama.cpp server (localhost:8080)
- Platform detection (Android/Termux, iOS/a-Shell, macOS, Linux)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
import asyncio


@dataclass
class DetectedModel:
    name: str
    provider: str  # ollama, lmstudio, localai, llamacpp
    size: str = ""
    quantization: str = ""
    modified: str = ""


@dataclass
class PlatformInfo:
    os: str  # android, ios, macos, linux, windows
    device: str  # termux, ashell, ish, desktop
    arch: str  # arm64, x86_64, etc.
    python_version: str = ""
    has_gpu: bool = False
    ram_mb: int = 0
    storage_free_gb: float = 0.0


@dataclass
class DetectionResult:
    platform: PlatformInfo
    local_models: list[DetectedModel] = field(default_factory=list)
    local_providers: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def detect_platform() -> PlatformInfo:
    """Detect what platform we're running on."""
    system = platform.system().lower()
    arch = platform.machine()
    py_version = platform.python_version()

    # Android / Termux detection
    if os.environ.get("TERMUX_VERSION") or os.path.exists("/data/data/com.termux"):
        return PlatformInfo(
            os="android", device="termux", arch=arch,
            python_version=py_version,
            ram_mb=_get_ram_mb(),
            storage_free_gb=_get_free_storage(),
        )

    # iOS / a-Shell detection
    if os.environ.get("ASHELL") or os.path.exists("/var/mobile"):
        return PlatformInfo(
            os="ios", device="ashell", arch=arch,
            python_version=py_version,
        )

    # iSH detection
    if os.path.exists("/dev/ish"):
        return PlatformInfo(
            os="ios", device="ish", arch="x86",
            python_version=py_version,
        )

    # macOS
    if system == "darwin":
        has_gpu = _check_mac_gpu()
        return PlatformInfo(
            os="macos", device="desktop", arch=arch,
            python_version=py_version,
            has_gpu=has_gpu,
            ram_mb=_get_ram_mb(),
            storage_free_gb=_get_free_storage(),
        )

    # Linux
    if system == "linux":
        has_gpu = _check_nvidia_gpu()
        return PlatformInfo(
            os="linux", device="desktop", arch=arch,
            python_version=py_version,
            has_gpu=has_gpu,
            ram_mb=_get_ram_mb(),
            storage_free_gb=_get_free_storage(),
        )

    # Windows
    if system == "windows":
        return PlatformInfo(
            os="windows", device="desktop", arch=arch,
            python_version=py_version,
            ram_mb=_get_ram_mb(),
        )

    return PlatformInfo(os=system, device="unknown", arch=arch, python_version=py_version)


async def detect_local_models() -> list[DetectedModel]:
    """Scan for locally running AI model servers."""
    models: list[DetectedModel] = []

    # Check Ollama
    ollama_models = await _scan_ollama()
    models.extend(ollama_models)

    # Check LM Studio
    lmstudio_models = await _scan_openai_compat("http://localhost:1234", "lmstudio")
    models.extend(lmstudio_models)

    # Check LocalAI
    localai_models = await _scan_openai_compat("http://localhost:8080", "localai")
    models.extend(localai_models)

    return models


async def _scan_ollama() -> list[DetectedModel]:
    """Check if Ollama is running and list its models."""
    models = []
    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("http://localhost:11434/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for m in data.get("models", []):
                        name = m.get("name", "")
                        size = m.get("size", 0)
                        size_str = f"{size / 1e9:.1f}GB" if size > 0 else ""
                        details = m.get("details", {})
                        quant = details.get("quantization_level", "")
                        modified = m.get("modified_at", "")
                        models.append(DetectedModel(
                            name=name, provider="ollama",
                            size=size_str, quantization=quant, modified=modified,
                        ))
    except Exception:
        pass
    return models


async def _scan_openai_compat(base_url: str, provider: str) -> list[DetectedModel]:
    """Check OpenAI-compatible servers (LM Studio, LocalAI, etc.)."""
    models = []
    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{base_url}/v1/models") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for m in data.get("data", []):
                        models.append(DetectedModel(
                            name=m.get("id", "unknown"),
                            provider=provider,
                        ))
    except Exception:
        pass
    return models


async def detect_all() -> DetectionResult:
    """Run full detection: platform + local models."""
    plat = detect_platform()
    models = await detect_local_models()

    # Build provider list
    providers = []
    ollama_models = [m for m in models if m.provider == "ollama"]
    if ollama_models:
        providers.append({
            "name": "ollama",
            "url": "http://localhost:11434",
            "models": [m.name for m in ollama_models],
        })

    lmstudio_models = [m for m in models if m.provider == "lmstudio"]
    if lmstudio_models:
        providers.append({
            "name": "lmstudio",
            "url": "http://localhost:1234",
            "models": [m.name for m in lmstudio_models],
        })

    localai_models = [m for m in models if m.provider == "localai"]
    if localai_models:
        providers.append({
            "name": "localai",
            "url": "http://localhost:8080",
            "models": [m.name for m in localai_models],
        })

    # Recommendations
    recs = _build_recommendations(plat, models)

    return DetectionResult(
        platform=plat,
        local_models=models,
        local_providers=providers,
        recommendations=recs,
    )


def _build_recommendations(plat: PlatformInfo, models: list[DetectedModel]) -> list[str]:
    recs = []

    if plat.device == "termux":
        recs.append("Running on Termux - cloud providers recommended for best performance")
        recs.append("Ollama can run on Termux with: pkg install ollama")
        if plat.ram_mb and plat.ram_mb < 6000:
            recs.append(f"Low RAM ({plat.ram_mb}MB) - use small models (1-3B params) or cloud only")

    elif plat.device == "ashell" or plat.device == "ish":
        recs.append("Running on iOS - cloud providers only (no local model support)")

    elif plat.os == "macos":
        if not models:
            recs.append("No local models detected - install Ollama: brew install ollama")
        if plat.has_gpu:
            recs.append("Apple Silicon GPU detected - local models will run well")
        if plat.ram_mb and plat.ram_mb >= 16000:
            recs.append(f"Good RAM ({plat.ram_mb}MB) - can run 7B-13B models locally")

    elif plat.os == "linux":
        if not models:
            recs.append("No local models detected - install Ollama: curl -fsSL https://ollama.com/install.sh | sh")
        if plat.has_gpu:
            recs.append("NVIDIA GPU detected - local models will be fast")

    if models:
        recs.append(f"Found {len(models)} local model(s): {', '.join(m.name for m in models[:5])}")

    return recs


def _get_ram_mb() -> int:
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(out.strip()) // (1024 * 1024)
        elif platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


def _get_free_storage() -> float:
    try:
        st = os.statvfs(".")
        return (st.f_bavail * st.f_frsize) / (1024 ** 3)
    except Exception:
        return 0.0


def _check_mac_gpu() -> bool:
    try:
        out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True)
        return "Apple" in out
    except Exception:
        return False


def _check_nvidia_gpu() -> bool:
    return shutil.which("nvidia-smi") is not None
