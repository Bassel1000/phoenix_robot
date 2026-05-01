To calculate the actual physical speed of your robot (in meters per second), you need to know three hardware specifications: the **Motor RPM**, the **Wheel Diameter**, and the **Load/Efficiency Drop**. 

Since you are controlling the motors via open-loop PWM (percentages), the speed calculation is theoretical. Here is the step-by-step formula to calculate it:

### 1. The Formula
First, find out the distance the robot travels in one wheel rotation (the circumference):
$$\text{Circumference (C)} = \pi \times \text{Wheel Diameter (in meters)}$$

Then, calculate the maximum theoretical speed at 100% power:
$$\text{Max Speed }(V_{max}) = \left(\frac{\text{Motor RPM}}{60}\right) \times C$$

To find the speed at 50% PWM power, you simply multiply the max speed by 0.5 (assuming a linear voltage-to-RPM relationship):
$$\text{Speed at 50\%} = V_{max} \times 0.5$$

### 2. An Example Calculation
Let's assume you are using common 12V DC Gear Motors and standard robot wheels.
*   **Wheel Diameter:** 10 cm (0.10 meters)
*   **Motor RPM** (at max voltage): 300 RPM 

**Step 1: Circumference**
$$C = 3.14159 \times 0.10 \text{ m} = 0.314 \text{ meters}$$
*(The robot moves 0.314 meters every time the wheel spins once).*

**Step 2: Max Speed (100% PWM)**
$$\text{Revolutions per second} = \frac{300 \text{ RPM}}{60} = 5 \text{ rev/sec}$$
$$V_{max} = 5 \text{ rev/sec} \times 0.314 \text{ m} = 1.57 \text{ meters/second}$$

**Step 3: Speed at 50% PWM**
$$V_{50\%} = 1.57 \text{ m/s} \times 0.5 = 0.785 \text{ meters/second}$$

### 3. Real-World Factors (Why it might be slower)
The theoretical math above assumes the motor is spinning freely in the air. On the ground, you need to account for physics:
*   **Load and Weight:** The weight of the robot dragging on the motors lowers the actual RPM compared to the manufacturer's rated "No-Load RPM".
*   **Battery Voltage Drop:** As your battery drains, the maximum voltage drops, which lowers the maximum RPM.
*   **Skid-Steer Friction:** Because you have 4 wheels, the motors fight against ground friction constantly.

**Rule of Thumb:** Expect your *actual* speed on the ground to be roughly **15% to 25% lower** than the theoretical math above. In the example above, the real speed at 50% power would be closer to `0.60 m/s`. 

*(Note: If you want exactly calculated, guaranteed speeds regardless of battery voltage or weight, you would need to add **Wheel Encoders** to the motors and implement PID control to implement closed-loop PID control so the robot can measure its own speed dynamically changing its PWM dynamically to maintain the exact target speed).*