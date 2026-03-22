#!/usr/bin/env python3

from pathlib import Path

import yaml


def scene_config_path(pkg_share: str, scene_name: str) -> Path:
    return Path(pkg_share) / 'scenes' / scene_name / 'scene.yaml'


def load_scene_profile(pkg_share: str, scene_name: str) -> dict:
    path = scene_config_path(pkg_share, scene_name)
    with path.open('r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def resolve_scene_world(pkg_share: str, scene_name: str) -> str:
    profile = load_scene_profile(pkg_share, scene_name)
    return str(Path(pkg_share) / profile['world'])


def resolve_scene_model_path(pkg_share: str, scene_name: str) -> str:
    profile = load_scene_profile(pkg_share, scene_name)
    model_path = profile.get('model_path')
    if not model_path:
        return ''
    return str(Path(pkg_share) / model_path)


def resolve_scene_map(pkg_share: str, scene_name: str) -> str:
    profile = load_scene_profile(pkg_share, scene_name)
    return str(Path(pkg_share) / profile['map'])


def resolve_scene_nav2_params(pkg_share: str, scene_name: str) -> str:
    profile = load_scene_profile(pkg_share, scene_name)
    nav2_params = profile.get('nav2_params', 'config/nav2_params.yaml')
    return str(Path(pkg_share) / nav2_params)


def resolve_scene_slam_nav2_params(pkg_share: str, scene_name: str) -> str:
    profile = load_scene_profile(pkg_share, scene_name)
    autonomy = profile.get('autonomy', {})
    slam_nav2_params = autonomy.get('slam_nav2_params', profile.get('nav2_params', 'config/nav2_params.yaml'))
    return str(Path(pkg_share) / slam_nav2_params)
