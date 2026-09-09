#!/usr/bin/env python3
"""Package one installed humanoid_gripper configuration for manager deployment."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import shutil
import tempfile

import yaml

from humanoid_manager.deployment import DeploymentError, pack_directory


PACKAGE = "humanoid_gripper"
PLUGIN_CLASS = "humanoid_gripper/RosTopicGripperDriver"
LIBRARY_NAME = "libhumanoid_ros_topic_gripper_driver.so"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installed_prefix", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--config",
        default="ros_topic_gripper.yaml",
        help="Configuration filename installed below share/humanoid_gripper/config.",
    )
    parser.add_argument("--plugin-id", default="humanoid_gripper_ros_topic")
    parser.add_argument("--name", default="ROS topic gripper adapter")
    parser.add_argument("--startup-config", type=Path,
                        help="Plugin startup YAML; defaults to config/<config stem>.startup.yaml if present.")
    return parser.parse_args()


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise DeploymentError(f"installed humanoid_gripper file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def plugin_metadata(config):
    """This adapter owns its private parameter contract and public test targets."""
    params = config['humanoid_gripper_runtime']['ros__parameters']
    properties = {'feedback_timeout_s': {'type': 'number', 'exclusiveMinimum': 0},
                  'startup_grace_s': {'type': 'number', 'minimum': 0}}
    required = []
    values = dict(entry.split('=', 1) for entry in params.get('plugin_parameters', []))
    capabilities = {}
    for index, name in enumerate(params['gripper_names']):
        rules = {
            'command_topic': {'type': 'string', 'pattern': r'^/[A-Za-z_][A-Za-z0-9_/]*$'},
            'feedback_topic': {'type': 'string', 'pattern': r'^/[A-Za-z_][A-Za-z0-9_/]*$'},
            'command_type': {'enum': ['float64', 'float64_multi_array', 'joint_state']},
            'feedback_type': {'enum': ['float64', 'joint_state']},
            'min_position': {'type': 'number'}, 'max_position': {'type': 'number'},
        }
        for key, rule in rules.items():
            properties[f'{name}.{key}'] = rule
            required.append(f'{name}.{key}')
        low, high = (float(values[f'{name}.{key}']) for key in ('min_position', 'max_position'))
        if not low < high:
            raise DeploymentError(f'{name}: min_position must be below max_position')
        # Limits are in vendor units; public capabilities use the platform mapping.
        scale = params.get('vendor_to_logical_scales', [1.] * len(params['gripper_names']))[index]
        offset = params.get('vendor_to_logical_offsets', [0.] * len(params['gripper_names']))[index]
        capabilities[name] = {'closed_position': low * scale + offset, 'open_position': high * scale + offset}
    # These constraints use Draft 7, which Ubuntu 22.04's system jsonschema supports.
    return {'parameter_schema': {'$schema': 'http://json-schema.org/draft-07/schema#',
                                 'type': 'object', 'properties': properties,
                                 'required': required, 'additionalProperties': False},
            'capabilities': {'grippers': capabilities}}


def main() -> int:
    args = arguments()
    installed = args.installed_prefix.resolve()
    config_relative = Path(args.config)
    if config_relative.name != args.config or config_relative.suffix not in {".yaml", ".yml"}:
        raise DeploymentError("--config must be one YAML filename")

    with tempfile.TemporaryDirectory(prefix="humanoid_gripper_bundle_") as temporary:
        root = Path(temporary) / "bundle"
        prefix = root / "prefix"
        installed_share = installed / "share" / PACKAGE
        for relative in (
            "package.xml",
            "plugins/gripper_plugins.xml",
            f"config/{args.config}",
        ):
            copy_file(installed_share / relative, prefix / "share" / PACKAGE / relative)
        copy_file(
            installed / "share/ament_index/resource_index/packages" / PACKAGE,
            prefix / "share/ament_index/resource_index/packages" / PACKAGE,
        )
        copy_file(
            installed / "lib" / LIBRARY_NAME,
            prefix / "lib" / LIBRARY_NAME,
        )

        architecture = platform.machine().lower()
        architecture = {"amd64": "x86_64", "arm64": "aarch64"}.get(
            architecture, architecture
        )
        manifest = {
            "schema_version": 1,
            "artifact_type": "plugin",
            "plugin_type": "gripper_driver",
            "plugin_id": args.plugin_id,
            "name": args.name,
            "compatibility": {
                "ros_distro": "humble",
                "architecture": architecture,
                "driver_interface_abi": 1,
            },
            "package_name": PACKAGE,
            "ament_prefix": "prefix",
            "plugin_xml": f"prefix/share/{PACKAGE}/plugins/gripper_plugins.xml",
            "library": f"prefix/lib/{LIBRARY_NAME}",
            "plugin_class": PLUGIN_CLASS,
            "resources": {
                "gripper_params": f"prefix/share/{PACKAGE}/config/{args.config}",
            },
        }
        manifest.update(plugin_metadata(yaml.safe_load((installed_share / 'config' / args.config).read_text())))
        startup_path = args.startup_config or (
            installed_share / "config" / config_relative.with_suffix('.startup.yaml'))
        if args.startup_config is not None or startup_path.is_file():
            with startup_path.open(encoding="utf-8") as stream:
                startup = yaml.safe_load(stream)
            from humanoid_manager.plugin_metadata import validate_settings
            templates = startup.pop('plugin_parameter_templates', {}) if isinstance(startup, dict) else {}
            settings = validate_settings(startup)
            if templates:
                target = root / manifest['resources']['gripper_params']
                config = yaml.safe_load(target.read_text())
                params = config['humanoid_gripper_runtime']['ros__parameters']
                entries = dict(entry.split('=', 1) for entry in params['plugin_parameters'])
                entries.update(templates)
                params['plugin_parameters'] = [f'{key}={value}' for key, value in entries.items()]
                target.write_text(yaml.safe_dump(config, sort_keys=False))
            manifest.update({key: value for key, value in settings.items() if key != "capabilities" or value})
        root.mkdir(parents=True, exist_ok=True)
        (root / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        pack_directory(root, args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
