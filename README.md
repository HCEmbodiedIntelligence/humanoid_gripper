# humanoid_gripper

This is an independent plugin-source repository at `teleop_ws/src/humanoid_gripper`,
not part of `robot_bringup`. Normal robot installations import a prebuilt gripper ZIP
through the manager page; they do not need this source checkout.

Repository: [HCEmbodiedIntelligence/humanoid_gripper](https://github.com/HCEmbodiedIntelligence/humanoid_gripper).

For plugin development, build this package against the installed platform interfaces:

```bash
cd teleop_ws
source install/setup.bash
colcon build --packages-select humanoid_gripper --cmake-clean-cache
source install/setup.bash
```

`--cmake-clean-cache` also handles migration from the old nested source path. Keep the
same symlink-install mode used by the rest of your workspace. The standalone Git history
retains the original gripper source commit extracted from `robot_bringup`.

This package is the extensible collection of gripper drivers and protocol adapters. It is independent
from arm drivers, robot kinematics, the motion server, and the Web manager.

`humanoid_gripper/RosTopicGripperDriver` maps one or more logical grippers to configurable
vendor ROS topics. Per gripper it supports:

- command: `sensor_msgs/msg/JointState`, `std_msgs/msg/Float64`, or
  `std_msgs/msg/Float64MultiArray`;
- feedback: `sensor_msgs/msg/JointState` or `std_msgs/msg/Float64`;
- logical position limits, linear/angular units, direction, and zero offset.

Specialized SDK, CAN, Action, reused third-party drivers, or dexterous-hand plugins can be added
alongside this class while keeping the same `GripperDriverPlugin` runtime contract. Existing drivers
that already expose ROS topics can be reused through this adapter without changing their code.

The plugin is loaded by `humanoid_gripper_runtime_node`. Platform-facing commands and feedback use
named `sensor_msgs/msg/JointState` topics, so `hc_teleop_recv` never publishes to vendor endpoints.

The included `openarmx_v10_bimanual.yaml` is only a configuration profile for reusing the generic
topic adapter. `config/v10_controllers/openarmx_v10_split_controllers.yaml` supplies separate
seven-joint arm and one-joint gripper ros2_control controllers. The accompanying
`openarmx_v10_bimanual.startup.yaml` declares controller initialization in the plugin manifest.
The normal registered-robot launch automatically ensures both controllers are active before
starting the HC runtimes; no manual gripper spawner command is needed. Restarting HC reuses
already active controllers. The vendor controller_manager must still load the split configuration.

After an isolated build, create an importable manager bundle with:

```bash
python3 src/humanoid_gripper/tools/create_deployment_bundle.py \
  install/humanoid_gripper deploy_artifacts/openarmx-gripper.zip \
  --config openarmx_v10_bimanual.yaml \
  --plugin-id openarmx_v10_bimanual_gripper \
  --name "OpenArmX v10 bimanual grippers"
```

Generated parameter schemas explicitly use JSON Schema Draft 7, supported by Ubuntu 22.04's
system `python3-jsonschema` package. Update both `humanoid_manager` and this packager when
migrating from bundles that required `Draft202012Validator`; rebuild/install the manager and
regenerate the ZIP. Installing Web dependencies alone does not update system Python.

`config/ros_topic_gripper.yaml` is the editable deployment template. Build the package, then create
an importable `gripper_driver` ZIP with:

```bash
python3 tools/create_deployment_bundle.py \
  "$(ros2 pkg prefix humanoid_gripper)" humanoid-gripper.zip
```

Import that ZIP on the humanoid_manager robot page. The page copies the selected plugin into the
robot version and keeps logical names, vendor endpoints, limits, and teleoperation mapping in sync.

The packager includes `config/<config stem>.startup.yaml` when present. Alternatively pass
`--startup-config /path/to/startup.yaml`, containing a single `startup` list. Each driver profile
declares its own dependencies; direct SDK/CAN grippers can omit startup steps entirely. The
generic manifest also supports vendor ROS nodes and launch files, with no robot-specific logic
in the manager. See `humanoid_manager/docs/deploying_plugins.md` for the schema.

After updating the manager and importing a new ZIP, select that source gripper plugin, save the
robot configuration, and restart it. Imported updates do not overwrite an existing saved private
plugin copy automatically. A robot configuration without a gripper plugin starts no gripper steps.

本包是 `GripperDriverPlugin` 的一个 ROS 话题派生实现。需要其他消息、Action、Service 或 SDK 的设备应提供对应派生插件，通用运行时无需识别其厂商。
打包器同时导出私有参数 schema 和统一单位的开合目标。`*.startup.yaml` 可声明实例变量；
本适配器打包器另支持 `plugin_parameter_templates`，用于生成可参数化的管理器资源，原始 ROS YAML 保持可直接使用。
多个插件或同插件的独立设备实例见 [设备实例说明](../humanoid_manager/docs/device_instances.md)。
