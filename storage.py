"""Respaldo del estado en un repositorio de datos de Hugging Face.

Los contenedores de HF Spaces son efímeros: al redesplegar o reiniciar,
el sistema de archivos vuelve al estado del código. Este módulo sube/baja
state.json, trades.jsonl, equity.jsonl y APRENDIDO.md a un repo dataset
privado para que el historial sobreviva.

Variables de entorno:
  HF_TOKEN       token de Hugging Face (permisos write)
  BOT_STATE_REPO repo dataset, p. ej. "usuario/paper-trading-bot-state"

Sin ambas variables (modo local), no hace nada.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
FILES = ["state.json", "trades.jsonl", "equity.jsonl", "APRENDIDO.md"]


def _enabled() -> bool:
    return bool(os.environ.get("HF_TOKEN") and os.environ.get("BOT_STATE_REPO"))


def _api():
    from huggingface_hub import HfApi
    return HfApi(token=os.environ["HF_TOKEN"])


def restore():
    """Descarga el estado respaldado si falta localmente (primer arranque)."""
    if not _enabled():
        return
    repo = os.environ["BOT_STATE_REPO"]
    try:
        api = _api()
        got = []
        for f in FILES:
            if os.path.exists(os.path.join(ROOT, f)):
                continue  # ya hay estado local: no pisar
            try:
                api.hf_hub_download(repo_id=repo, filename=f, repo_type="dataset", local_dir=ROOT)
                got.append(f)
            except Exception:
                pass  # archivo aún no respaldado (primera vez)
        print(f"[storage] restore desde {repo}: {'restaurados ' + ', '.join(got) if got else 'nada que restaurar'}")
    except Exception as e:
        print(f"[storage] restore omitido: {e}")


def backup():
    """Sube el estado actual al repo dataset (best-effort: un fallo no detiene al bot)."""
    if not _enabled():
        return
    repo = os.environ["BOT_STATE_REPO"]
    try:
        api = _api()
        api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
        for f in FILES:
            path = os.path.join(ROOT, f)
            if os.path.exists(path):
                api.upload_file(
                    path_or_fileobj=path,
                    path_in_repo=f,
                    repo_id=repo,
                    repo_type="dataset",
                )
        print(f"[storage] backup → {repo} OK")
    except Exception as e:
        print(f"[storage] backup omitido: {e}")
