(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
{attribute 'qualified_only'}
VAR_GLOBAL
    (* motor_command -- 0x00000100, pc_to_plc *)
    targetVelocity_rpm        : REAL;
    torqueLimit_Nm            : REAL;
    motorCommandWithinTimeout : BOOL;

    (* pc_state -- 0x00000300, pc_to_plc *)
    driveMode                 : DriveMode;
    pcStateWithinTimeout      : BOOL;
END_VAR
