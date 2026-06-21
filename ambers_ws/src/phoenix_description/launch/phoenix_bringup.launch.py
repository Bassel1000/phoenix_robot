import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Lidar Publisher
    lidar_node = Node(
        package='phoenix_control',
        executable='lidar_publisher',
        name='lidar_publisher'
    )

    # 2. Laser Odometry & Transforms
    phoenix_desc_dir = get_package_share_directory('phoenix_description')
    laser_odom_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(phoenix_desc_dir, 'launch', 'laser_odom.launch.py')
        )
    )

    # 3. SLAM Toolbox
    slam_toolbox_dir = get_package_share_directory('slam_toolbox')
    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_toolbox_dir, 'launch', 'online_async_launch.py')
        ),
        launch_arguments={
            'slam_params_file': os.path.join(phoenix_desc_dir, 'config', 'mapper_params_online_async.yaml'),
            'use_sim_time': 'False'
        }.items()
    )

    # 4. Nav2 Stack
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'False',
            'params_file': os.path.join(phoenix_desc_dir, 'config', 'nav2_params.yaml')
        }.items()
    )

    # 5. Motor Controller
    motor_node = Node(
        package='phoenix_control',
        executable='motor_controller',
        name='motor_controller'
    )

    # 6. MQTT Navigation Client
    mqtt_nav_node = Node(
        package='phoenix_control',
        executable='mqtt_nav_client',
        name='mqtt_nav_client'
    )

    # 7. Pump Controller
    pump_node = Node(
        package='phoenix_control',
        executable='pump_controller',
        name='pump_controller'
    )

    # 8. Nozzle Controller
    nozzle_node = Node(
        package='phoenix_control',
        executable='nozzle_controller',
        name='nozzle_controller'
    )


    # 10. MQTT Motor Bridge
    mqtt_bridge_node = Node(
        package='phoenix_control',
        executable='mqtt_motor_bridge',
        name='mqtt_motor_bridge'
    )

    return LaunchDescription([
        lidar_node,
        laser_odom_launch,
        slam_launch,
        nav2_launch,
        motor_node,
        mqtt_nav_node,
        pump_node,
        nozzle_node,
        mqtt_bridge_node
    ])
