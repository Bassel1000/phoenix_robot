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

    # 3. Publish Laser Odometry (odom -> base_link) using LiDAR scans
    rf2o_laser_odometry_node = Node(
        package='rf2o_laser_odometry',
        executable='rf2o_laser_odometry_node',
        name='rf2o_laser_odometry',
        output='screen',
        parameters=[{
            'laser_scan_topic': '/scan',
            'odom_topic': '/odom',
            'publish_tf': True,
            'base_frame_id': 'base_link',
            'odom_frame_id': 'odom',
            'laser_frame_id': 'lidar_link', # Must match the frame name in your URDF/LiDAR driver
            'init_pose_from_topic': '',      # Crucial: Disable waiting for ground truth pose
            'freq': 10.0 # Frequency of odometry computation (Hz)
        }]
    )

    return LaunchDescription([
        robot_state_publisher_node,
        joint_state_publisher_node,
        rf2o_laser_odometry_node
    ])
