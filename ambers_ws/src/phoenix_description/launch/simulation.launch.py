import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    description_share = get_package_share_directory("phoenix_description")
    gazebo_share = get_package_share_directory("ros_gz_sim")
    slam_share = get_package_share_directory("slam_toolbox")
    nav2_share = get_package_share_directory("nav2_bringup")

    world_file = os.path.join(description_share, "worlds", "phoenix_test_world.sdf")
    simulation_model = os.path.join(description_share, "models", "phoenix_sim.sdf")
    urdf_file = os.path.join(description_share, "urdf", "phoenix.urdf")
    nav2_params = os.path.join(description_share, "config", "nav2_params.yaml")
    slam_params = os.path.join(
        description_share, "config", "mapper_params_online_async.yaml"
    )
    rviz_config = os.path.join(description_share, "config", "phoenix_sim.rviz")

    launch_mqtt = LaunchConfiguration("launch_mqtt")
    declare_launch_mqtt = DeclareLaunchArgument(
        "launch_mqtt",
        default_value="true",
        description="Whether to launch MQTT bridge and control nodes for Web Command Center integration",
    )

    launch_rviz = LaunchConfiguration("rviz")
    declare_launch_rviz = DeclareLaunchArgument(
        "rviz",
        default_value="false",
        description="Whether to launch RViz2 for LiDAR, SLAM, and robot visualization",
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

    # MQTT Bridge nodes for full Web Command Center and AI vision node integration
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

    # Give Gazebo, the bridge, and SLAM time to establish map -> odom before
    # Nav2 activates its global costmap.
    delayed_nav2 = TimerAction(period=8.0, actions=[nav2])

    set_rmw = SetEnvironmentVariable(
        name="RMW_IMPLEMENTATION", value="rmw_cyclonedds_cpp"
    )

    return LaunchDescription(
        [
            set_rmw,
            declare_launch_mqtt,
            declare_launch_rviz,
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
    )
