(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION DriveMode_FROM_INT : DriveMode
VAR_INPUT
    value : USINT;
END_VAR

// --- BEGIN IMPLEMENTATION ---

CASE value OF
    0: DriveMode_FROM_INT := DriveMode.IDLE;
    1: DriveMode_FROM_INT := DriveMode.VELOCITY;
    2: DriveMode_FROM_INT := DriveMode.POSITION;
    3: DriveMode_FROM_INT := DriveMode.TORQUE;
ELSE
    DriveMode_FROM_INT := DriveMode.IDLE;
END_CASE
