from setuptools import find_packages, setup

package_name = 'phoenix_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Bassel Ashraf Ahmed Elbahnasy',
    maintainer_email='basse@todo.todo',
    description='Hardware control nodes for the Phoenix robot.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'motor_controller = phoenix_control.motor_controller:main',
            'pump_controller = phoenix_control.pump_controller:main',
            'lidar_publisher = phoenix_control.lidar_publisher:main',
            'mqtt_nav_client = phoenix_control.mqtt_nav_client:main',
        ],
    },
)