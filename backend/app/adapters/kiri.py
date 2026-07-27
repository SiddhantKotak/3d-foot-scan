"""KIRI Engine adapter — real HTTP client + mock mode.

Mock mode (no KIRI_API_KEY): submit returns a fake serial, status reports
success immediately, and "download" copies a local mesh into the scan dir, so
the pipeline runs end-to-end without credentials. The real code paths are built
to the documented contract and activate the moment a key is present.

KIRI docs: base https://api.kiriengine.app/api/v1 ; Bearer auth ; every response
is {code, msg, data, ok}. Status ints: -1 uploading, 0 processing, 1 failed,
2 success, 3 queuing, 4 expired. Download link (getModelZip -> data.modelUrl)
expires in 60 minutes -> fetch immediately on success.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import os
import shutil
import zipfile
from dataclasses import dataclass

import httpx

from ..config import Settings

# KIRI status codes
STATUS_UPLOADING, STATUS_PROCESSING, STATUS_FAILED = -1, 0, 1
STATUS_SUCCESS, STATUS_QUEUING, STATUS_EXPIRED = 2, 3, 4
_MESH_EXTS = (".obj", ".ply", ".stl", ".glb", ".gltf")


@dataclass
class KiriClient:
    settings: Settings

    @property
    def live(self) -> bool:
        return self.settings.kiri_live

    # --- shared ---
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.kiri_api_key}"}

    def _url(self, path: str) -> str:
        return f"{self.settings.kiri_base_url.rstrip('/')}{path}"

    # --- submit ---
    def submit_photo_scan(self, image_paths: list[str], *, file_format: str = "obj",
                          model_quality: int = 0, texture_quality: int = 0,
                          is_mask: int = 0) -> str:
        """Submit a photogrammetry job; return the KIRI serialize (task id).

        is_mask=1 tells KIRI the input carries a foreground mask (transparent
        PNG / alpha), so it reconstructs only the masked subject — used to strip
        the floor/clutter that otherwise fuses into the foot mesh.
        """
        if not self.live:
            return "MOCK-" + hashlib.sha1("".join(image_paths).encode()).hexdigest()[:16]
        files = [("imagesFiles", (os.path.basename(p), open(p, "rb"),
                  "image/png" if p.lower().endswith(".png") else "image/jpeg"))
                 for p in image_paths]
        data = {"modelQuality": str(model_quality), "textureQuality": str(texture_quality),
                "fileFormat": file_format, "isMask": str(is_mask)}
        with httpx.Client(timeout=300) as c:
            r = c.post(self._url("/open/photo/image"), headers=self._headers(),
                       data=data, files=files)
            r.raise_for_status()
            body = r.json()
        if not body.get("ok", body.get("code") == 0):
            raise RuntimeError(f"KIRI submit failed: {body}")
        return body["data"]["serialize"]

    def submit_featureless_scan(self, image_paths: list[str], *, file_format: str = "obj") -> str:
        """Submit a Featureless Object Scan — KIRI's mode for smooth/low-texture
        objects (a bare foot), which standard photogrammetry struggles to match
        features on. Endpoint: POST /open/featureless/image (imagesFiles + fileFormat)."""
        if not self.live:
            return "MOCK-" + hashlib.sha1(("fl" + "".join(image_paths)).encode()).hexdigest()[:16]
        files = [("imagesFiles", (os.path.basename(p), open(p, "rb"),
                  "image/png" if p.lower().endswith(".png") else "image/jpeg"))
                 for p in image_paths]
        with httpx.Client(timeout=300) as c:
            r = c.post(self._url("/open/featureless/image"), headers=self._headers(),
                       data={"fileFormat": file_format}, files=files)
            r.raise_for_status()
            body = r.json()
        if not body.get("ok", body.get("code") == 0):
            raise RuntimeError(f"KIRI featureless submit failed: {body}")
        return body["data"]["serialize"]

    # --- poll ---
    def get_status(self, serialize: str) -> int:
        if not self.live:
            return STATUS_SUCCESS
        with httpx.Client(timeout=30) as c:
            r = c.get(self._url("/open/model/getStatus"), headers=self._headers(),
                      params={"serialize": serialize})
            r.raise_for_status()
            return int(r.json()["data"]["status"])

    def get_download_url(self, serialize: str) -> str:
        if not self.live:
            return "mock://" + serialize
        with httpx.Client(timeout=30) as c:
            r = c.get(self._url("/open/model/getModelZip"), headers=self._headers(),
                      params={"serialize": serialize})
            r.raise_for_status()
            return r.json()["data"]["modelUrl"]

    # --- fetch mesh (must happen within the 60-min link window) ---
    def download_mesh(self, serialize: str, url: str, dest_dir: str) -> str:
        os.makedirs(dest_dir, exist_ok=True)
        if not self.live:
            src = self.settings.mock_mesh_path
            dst = os.path.join(dest_dir, "model" + os.path.splitext(src)[1])
            shutil.copyfile(src, dst)
            return dst
        with httpx.Client(timeout=300, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            content = r.content
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            mesh_name = next((n for n in z.namelist() if n.lower().endswith(_MESH_EXTS)), None)
            if mesh_name is None:
                raise RuntimeError(f"no mesh in KIRI zip: {z.namelist()}")
            z.extract(mesh_name, dest_dir)
            return os.path.join(dest_dir, mesh_name)

    # --- webhook verification ---
    @staticmethod
    def verify_webhook(task_id: str, timestamp: str, signature: str, secret: str) -> bool:
        """signature = base64(HMAC_SHA256(taskId + '.' + timestamp, secret)),
        compared in constant time."""
        expected = base64.b64encode(
            hmac.new(secret.encode(), f"{task_id}.{timestamp}".encode(), hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(expected, signature)
