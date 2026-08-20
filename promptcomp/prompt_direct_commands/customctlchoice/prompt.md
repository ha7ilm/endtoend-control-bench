You are an expert control engineer. I want you to design and implement a controller based on the following documents available to you: 

- `problem_description.md`: description of the plant and the design goals, 
- `howto_for_control_loop_software.md`: description of the communication interface. 

## 1) Design task
Your first task is to:
- analyze the plant based on the model equations,
- choose the control design technique that is most suitable,
- design the controller, 
- evaluate it through the computer interface. 
- Iterate the design until you **meet the design specifications**. 

As you iterate, I want you to create a new script for every controller that you evaluate: `controller_1.py`, `controller_2.py`,...
In this phase, start the "why" field of MachineClient with "Design to meet specifications: "

## 2) Tuning task
Once you managed to meet the design specification, I would like that you further tune the controller, with the following goal:
%{aircraftpitch_dt, ballandbeam_dt, ballandbeam_dt_nl_act_mg996r,  motorspeed_dt_lim_maxonre30,  motorspeed_dt: minimize `overshoot_pct + 3*settling_time_sec`.}%
%{invertedpendulum_dt_nl_lim_quanserip02,invertedpendulum_dt: minimize `machine_msg["kpis"]["channels"]["x_cart"]["settling_time_sec"] + 2*machine_msg["kpis"]["channels"]["x_cart"]["steady_state_error_pct"] + machine_msg["kpis"]["channels"]["phi_angle"]["settling_time_sec"] + 2*machine_msg["kpis"]["channels"]["phi_angle"]["steady_state_error_pct"]`.}%
%{cruisecontrol_dt_lim_hondajazz, cruisecontrol_dt: minimize `overshoot_pct+2*rise_time_sec`.}%
In this phase, start the "why" field of MachineClient with "Tuning: "

## 3) Making conclusions
I want you to create two more files:
- `best.txt` that contains only the name of the script corresponding to the controller that you think is best, like `controller_N.py`. 
- `summary.md` that summarizes how did the analysis, design and tuning go, what were the main challenges and main decisions taken.
