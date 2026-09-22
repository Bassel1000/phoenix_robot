import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context, *args, **kwargs):
    description_share = get_package_share_directory("phoenix_description")
    gazebo_share = get_package_share_directory("ros_gz_sim")
    slam_share = get_package_share_directory("slam_toolbox")
    nav2_share = get_package_share_directory("nav2_bringup")

    urdf_file = os.path.join(description_share, "urdf", "phoenix.urdf")
    nav2_params = os.path.join(description_share, "config", "nav2_params.yaml")
    slam_params = os.path.join(
        description_share, "config", "mapper_params_online_async.yaml"
    )
    rviz_config = os.path.join(description_share, "config", "phoenix_sim.rviz")

    world_type_str = context.perform_substitution(
        LaunchConfiguration("world_type")
    ).lower()
    pro_model_str = context.perform_substitution(
        LaunchConfiguration("pro_model")
    ).lower()
    run_demo_str = context.perform_substitution(
        LaunchConfiguration("run_demo")
    ).lower()
    launch_mqtt = LaunchConfiguration("launch_mqtt")
    launch_rviz = LaunchConfiguration("rviz")

    # Select environment world and spawn pose
    if world_type_str == "datacenter":
        world_filename = "phoenix_datacenter_world.sdf"
        spawn_x = "-0.5"
        spawn_y = "0.0"
        spawn_z = "0.05"
        spawn_yaw = "0.0"
    elif world_type_str == "warehouse":
        world_filename = "phoenix_warehouse_world.sdf"
        spawn_x = "-0.5"
        spawn_y = "0.0"
        spawn_z = "0.05"
        spawn_yaw = "0.0"
    else:
        world_filename = "phoenix_test_world.sdf"
        spawn_x = "0.0"
        spawn_y = "0.0"
        spawn_z = "0.05"
        spawn_yaw = "0.0"

    world_file = os.path.join(description_share, "worlds", world_filename)

    # Select robot visual model
    if pro_model_str in ["true", "1", "yes"]:
        simulation_model = os.path.join(
            description_share, "models", "phoenix_pro_sim.sdf"
        )
    else:
        simulation_model = os.path.join(
            description_share, "models", "phoenix_sim.sdf"
        )

    with open(urdf_file, "r", encoding="utf-8") as robot_file:
        robot_description = robot_file.read()

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": f"-r -v 4 {world_file}"}.items(),
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[{"robot_description": robot_description, "use_sim_time": True}],
        output="screen",
    )

    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-file",
            simulation_model,
            "-name",
            "phoenix",
            "-x",
            spawn_x,
            "-y",
            spawn_y,
            "-z",
            spawn_z,
            "-Y",
            spawn_yaw,
        ],
        output="screen",
    )

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
            "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
            "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
            "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image",
        ],
        output="screen",
    )

    odom_tf = Node(
        package="phoenix_control",
        executable="simulation_odom_tf",
        parameters=[{"use_sim_time": True}],
        output="screen",
    )

    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_share, "launch", "online_async_launch.py")
        ),
        launch_arguments={
            "slam_params_file": slam_params,
            "use_sim_time": "True",
        }.items(),
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_share, "launch", "navigation_launch.py")
        ),
        launch_arguments={
            "use_sim_time": "True",
            "params_file": nav2_params,
        }.items(),
    )

    mqtt_nav = Node(
        package="phoenix_control",
        executable="mqtt_nav_client",
        parameters=[{"use_sim_time": True}],
        output="screen",
        condition=IfCondition(launch_mqtt),
    )

    mqtt_motor = Node(
        package="phoenix_control",
        executable="mqtt_motor_bridge",
        parameters=[{"use_sim_time": True}],
        output="screen",
        condition=IfCondition(launch_mqtt),
    )

    pump = Node(
        package="phoenix_control",
        executable="pump_controller",
        parameters=[{"use_sim_time": True}],
        output="screen",
        condition=IfCondition(launch_mqtt),
    )

    nozzle = Node(
        package="phoenix_control",
        executable="nozzle_controller",
        parameters=[{"use_sim_time": True}],
        output="screen",
        condition=IfCondition(launch_mqtt),
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config],
        parameters=[{"use_sim_time": True}],
        output="screen",
        condition=IfCondition(launch_rviz),
    )

    # 18-second delay to allow Gazebo, bridge, and SLAM to stabilize
    delayed_nav2 = TimerAction(period=18.0, actions=[nav2])

    nodes_to_start = [
        gazebo,
        robot_state_publisher,
        spawn_robot,
        bridge,
        odom_tf,
        slam,
        delayed_nav2,
        mqtt_nav,
        mqtt_motor,
        pump,
        nozzle,
        rviz_node,
    ]

    # Optional automated competition demo director execution
    if run_demo_str in ["true", "1", "yes"]:
        demo_node = Node(
            package="phoenix_control",
            executable="competition_demo_director",
            arguments=["--world", world_type_str],
            parameters=[{"use_sim_time": True}],
            output="screen",
        )
        delayed_demo = TimerAction(period=22.0, actions=[demo_node])
        nodes_to_start.append(delayed_demo)

    return nodes_to_start


def generate_launch_description():
    set_rmw = SetEnvironmentVariable(
        name="RMW_IMPLEMENTATION", value="rmw_cyclonedds_cpp"
    )

    declare_world_type = DeclareLaunchArgument(
        "world_type",
        default_value="datacenter",
        description="Environment world: 'datacenter', 'warehouse', or 'test'",
    )

    declare_pro_model = DeclareLaunchArgument(
        "pro_model",
        default_value="true",
        description="Whether to use the high-fidelity Phoenix Pro visual robot model",
    )

    declare_run_demo = DeclareLaunchArgument(
        "run_demo",
        default_value="false",
        description="Automatically trigger the 6-stage competition demo sequence after Nav2 startup",
    )

    declare_launch_mqtt = DeclareLaunchArgument(
        "launch_mqtt",
        default_value="true",
        description="Whether to launch MQTT bridge and control nodes for Web Command Center integration",
    )

    declare_launch_rviz = DeclareLaunchArgument(
        "rviz",
        default_value="false",
        description="Whether to launch RViz2 for LiDAR, SLAM, and robot visualization",
    )

    return LaunchDescription(
        [
            set_rmw,
            declare_world_type,
            declare_pro_model,
            declare_run_demo,
            declare_launch_mqtt,
            declare_launch_rviz,
            OpaqueFunction(function=launch_setup),
        ]
    )
