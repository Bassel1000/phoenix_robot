import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_share = get_package_share_directory('phoenix_description')
    urdf_file_path = os.path.join(pkg_share, 'urdf', 'phoenix.urdf')

    with open(urdf_file_path, 'r') as f:
        robot_description = f.read()

    # 1. Publish robot description TF (base_link -> lidar_link, etc.)
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': False
        }]
    )

    # 2. Publish default joint states (since we have no encoders/sensors for joints)
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        parameters=[{
            'use_sim_time': False
        }]
    )
    static_odom_node = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_odom_publisher',
        arguments=['0', '0', '0', '0', '0', '0', 'odom', 'base_footprint']
    )

    return LaunchDescription([
        robot_state_publisher_node,
        joint_state_publisher_node
    ])
