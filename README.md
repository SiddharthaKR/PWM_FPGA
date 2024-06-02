# PWM Generator
## What is PWM?
**Pulse Width Modulation** is a technique of controlling the average voltage. It is a stream of voltage pulses that reduces the electric power supplied by the electrical signal. It is a square wave signal, which is represented as:

<picture> <img width="318" alt="image" src="https://github.com/Gurusatwik/PWM-Generator/assets/113631826/a2c1c02f-ba71-44c8-aacd-cfa70b39a7bf">

This implies that PWM has only 2 outputs i.e.,
- HIGH (LOGIC 1).
- LOW (LOGIC 0).
The duty cycle of the rectangular pulse is shown as follows:

<picture> <img width="147" alt="image" src="https://github.com/Gurusatwik/PWM-Generator/assets/113631826/23dc928f-69db-4969-8034-d0386e258d60">

where,
- t<sub>o</sub> is the time period for which the signal is LOGIC 1.
- t<sub>c</sub> is the total time period of the signal.

For example, let us assume that our output signal is having a timeperiod of 20ns,
- 0% Duty cycle implies that the signal is HIGH for 0ns and LOW for 20ns.
- 25% Duty cycle implies that the signal is HIGH for 5ns and LOW for 15ns.
- 50% Duty cycle implies that the signal is HIGH for 10ns and LOW for 10ns.
- 75% Duty cycle implies that the signal is HIGH for 15ns and LOW for 5ns.
- 100% Duty cycle implies that the signal is HIGH for 20ns and LOW for 0ns.

<picture> <img width="395" alt="image" src="https://github.com/Gurusatwik/PWM-Generator/assets/113631826/c34db129-52d8-45d6-84ef-3c7c9a838465">

## Applications
- Voltage regulation
- Audio signal generation
- Pump Hydraulics
- Servo motor
- CPU fan speed control
- Encoding in Telecommunication
- Motor speed controller

## PWM Generator using Verilog-HDL
PWM generator was designed in Verilog-HDL using `Xilinx Vivado 2022.2`. There are few changes that has to be done in the Simulation time.
### How to create a project in Xilinx Vivado 2022.2?
- **Step 1:** Open Vivado 2022.2 on your system.

<picture> <img width="130" alt="Untitled" src="https://github.com/Gurusatwik/PWM-Generator/assets/113631826/fb8d2d62-f2eb-45aa-b5d3-49ce2d021e55">

- **Step 2:** Create a new project as follows:
`create project` --> `Next` --> `Project name: ____` --> `Next` --> check `RTL Project` --> `Next` --> click on `Create File` --> a dialog bx pops up prompting you to give the `File name: ______` and click on `Next` --> `Next`.

- **Step 3:** Select an FPGA board
`Category: General Purpose` --> `Family: Atrix-7` --> `Package: csg324` --> `Speed: -1` --> select `xc7a100tcsg324-1` --> `Next` --> `Finish`.

- **Step 4:** I/O Constraints (optional)
***can proceed even without giving the constraints just by clicking on Finish/Next as it can be defined in the module later***.

### How to change Simulation time?
As soon as you open your project click on settings icon provided in the tool bar as shown below.

<picture> <img width="488" alt="Untitled1" src="https://github.com/Gurusatwik/PWM-Generator/assets/113631826/01744031-5d9b-4375-9ec9-a6a5f0d4287e">

This will pop up another Dialog box as shown below.

<picture> <img width="650" alt="Untitled3" src="https://github.com/Gurusatwik/PWM-Generator/assets/113631826/06303302-008a-4274-9ade-ca23a8faf371">

***Follow the numbers (from 1 - 4)*** <br />
The simulation time will be set to 1000ns by default. It can be changed according to our requirements.

- Now copy paste the codes `Variable_PWM.v` and `Variable_PWM_tb.v` file one below the other and click on `Run Simulation` --> `Run Behavioral Simulation` to see the output waveform.

## Schematic
<picture> <img width="788" alt="Untitled5" src="https://github.com/Gurusatwik/PWM-Generator/assets/113631826/7b732a40-5c6d-46f3-a31c-8143d6c234ce">

## Waveform
<picture> <img width="788" alt="Untitled4" src="https://github.com/Gurusatwik/PWM-Generator/assets/113631826/6b093022-94de-4018-90a3-f66f2a806dcd">

## Useful  links
- https://www.javatpoint.com/arduino-pwm
- https://www.xilinx.com/support/download/index.html/content/xilinx/en/downloadNav/vivado-design-tools/2022-2.html
- https://www.chipverify.com/verilog/verilog-tutorial
