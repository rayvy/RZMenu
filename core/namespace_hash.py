"""RZM namespace hash helpers.

Namespace format:
    RZM + author initial + base8 + skin4

Example:
    Resource\\RZMRB7CEF824969D\\YixuanBodyA = ref ResourceComputedResult
"""

from __future__ import annotations

import getpass
import hashlib
import os
import platform
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any


XXMI_GAMES = {"GenshinImpact", "ZenlessZoneZero", "HonkaiStarRail"}
PROJECT_SEED_PROP = "RZM_NAMESPACE_PROJECT_SEED"


@dataclass(frozen=True)
class RZMNamespace:
    base8: str
    skin4: str
    hash12: str
    namespace: str
    full: str
    author_initial: str
    character_name: str
    author_name: str
    skin_name: str
    project_seed: str
    is_project_seed_explicit: bool


def make_project_seed() -> str:
    return secrets.token_hex(8).upper()


def sanitize_name(value: Any, fallback: str = "CharacterName") -> str:
    value = str(value or "").strip() or fallback
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[^A-Za-z0-9_.@-]+", "_", value)
    return value.strip("._-") or fallback


def author_initial(author_name: str) -> str:
    for char in str(author_name or ""):
        if char.isalnum():
            return char.upper()
    return "X"


def set_project_seed(context: Any, seed: str | None = None) -> str:
    seed = str(seed or make_project_seed()).strip().upper()
    context.scene[PROJECT_SEED_PROP] = seed
    return seed


def get_project_seed(context: Any, target_path: str | None = None, *, create: bool = False) -> tuple[str, bool]:
    scene = context.scene
    existing = str(scene.get(PROJECT_SEED_PROP, "") or "").strip()
    if existing:
        return existing, True
    if create:
        return set_project_seed(context), True

    blend_path = str(getattr(__import__("bpy").data, "filepath", "") or "")
    material = "|".join(
        [
            "DERIVED",
            blend_path,
            str(target_path or ""),
            str(getattr(scene, "name", "") or ""),
        ]
    )
    derived = hashlib.blake2s(material.encode("utf-8"), digest_size=8).hexdigest().upper()
    return derived, False


def resolve_author_name(context: Any) -> str:
    candidates = []
    package_root = (__package__ or "").split(".")[0]
    if package_root:
        candidates.append(package_root)
    candidates.extend(["RZMenu", "RZMenu-master"])

    addons = getattr(getattr(context, "preferences", None), "addons", None)
    if addons:
        for name in candidates:
            prefs_entry = addons.get(name)
            prefs = getattr(prefs_entry, "preferences", None) if prefs_entry else None
            author = str(getattr(prefs, "author_name", "") or "").strip()
            if author:
                return author
        for prefs_entry in addons:
            prefs = getattr(prefs_entry, "preferences", None)
            author = str(getattr(prefs, "author_name", "") or "").strip()
            if author and hasattr(prefs, "artist_profiles"):
                return author

    return getpass.getuser() or "UNKNOWN"


def resolve_skin_name(context: Any) -> str:
    meta = context.scene.rzm.meta_data
    return str(getattr(meta, "outfit_name", "") or "").strip() or "DefaultSkin"


def _basename_from_path(path: Any) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    value = value.rstrip("\\/")
    return Path(value).name.strip()


def get_prefix_letters(name: str, count: int, fallback: str) -> str:
    letters = ""
    for char in str(name or ""):
        if char.isalnum():
            letters += char.upper()
            if len(letters) == count:
                break
    while len(letters) < count:
        letters += fallback
    return letters


def resolve_character_name(context: Any, export_cache: dict | None = None, target_path: str | None = None) -> str:
    rzm = context.scene.rzm
    meta = rzm.meta_data
    char_name = str(getattr(meta, "character_name", "") or "").strip()
    if char_name and char_name != "Fluorite":
        return sanitize_name(char_name)

    game = getattr(rzm.game, "selection", getattr(rzm.game, "name", ""))
    if game in XXMI_GAMES:
        xxmi = getattr(context.scene, "xxmi", None)
        dump_name = _basename_from_path(getattr(xxmi, "dump_path", "")) if xxmi else ""
        if dump_name:
            return sanitize_name(dump_name)

        cache_mod = str((export_cache or {}).get("mod_name", "") or "").strip()
        if cache_mod:
            return sanitize_name(cache_mod)

        folder_name = _basename_from_path(target_path)
        if folder_name:
            return sanitize_name(folder_name.lstrip("@"))

    return sanitize_name(char_name, fallback="CharacterName")


def build_namespace(
    *,
    character_name: str,
    author_name: str,
    skin_name: str,
    project_seed: str,
    os_name: str | None = None,
    user_name: str | None = None,
    is_project_seed_explicit: bool = True,
) -> RZMNamespace:
    os_name = os_name or platform.system() or os_name or "OS"
    user_name = user_name or getpass.getuser() or "USER"

    clean_character = sanitize_name(character_name)
    clean_author = str(author_name or "UNKNOWN").strip()
    clean_skin = str(skin_name or "DefaultSkin").strip()
    clean_seed = sanitize_name(project_seed, "SEED")

    author_prefix = get_prefix_letters(clean_author, 2, "X")
    char_prefix = get_prefix_letters(clean_character, 2, "C")

    base_material = "|".join(
        [
            clean_character,
            sanitize_name(clean_author, "Author"),
            sanitize_name(os_name, "OS"),
            sanitize_name(user_name, "USER"),
            clean_seed,
        ]
    )
    skin_material = "|".join([clean_character, sanitize_name(clean_skin, "Skin")])

    base4 = hashlib.blake2s(base_material.encode("utf-8"), digest_size=2).hexdigest().upper()
    skin2 = hashlib.blake2s(skin_material.encode("utf-8"), digest_size=1).hexdigest().upper()
    hash6 = f"{base4}{skin2}"
    namespace = f"{author_prefix}{char_prefix}{hash6}"
    return RZMNamespace(
        base8=base4,
        skin4=skin2,
        hash12=hash6,
        namespace=namespace,
        full=namespace,
        author_initial=author_prefix,
        character_name=clean_character,
        author_name=clean_author,
        skin_name=clean_skin,
        project_seed=clean_seed,
        is_project_seed_explicit=is_project_seed_explicit,
    )


def namespace_from_context(
    context: Any,
    export_cache: dict | None = None,
    target_path: str | None = None,
    *,
    create_seed: bool = False,
) -> RZMNamespace:
    seed, explicit = get_project_seed(context, target_path=target_path, create=create_seed)
    character = resolve_character_name(context, export_cache=export_cache, target_path=target_path)
    author = resolve_author_name(context)
    skin = resolve_skin_name(context)
    return build_namespace(
        character_name=character,
        author_name=author,
        skin_name=skin,
        project_seed=seed,
        is_project_seed_explicit=explicit,
    )
