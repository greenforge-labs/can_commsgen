(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION_BLOCK MOTOR_COMMAND_RECV
VAR_INPUT
    channel : ifmDevice.CAN_CHANNEL;
END_VAR
VAR
    rx     : ifmRCAN.CAN_Rx;
    timer  : TON;
    rxData : ARRAY[0..7] OF USINT;
END_VAR

// --- BEGIN IMPLEMENTATION ---

rx(xEnable := TRUE, eChannel := channel, xExtended := TRUE, udiID := 16#00000100);

IF rx.uiAvailable > 0 AND rx.usiDLC = 4 THEN
    rxData := rx.aData;
    GVL.targetVelocity_rpm := TO_REAL(CAN_EXTRACT_BITS(rxData, 0, 16, TRUE)) * 0.1;
    GVL.torqueLimit_Nm     := TO_REAL(CAN_EXTRACT_BITS(rxData, 16, 16, FALSE)) * 0.01;
    timer(IN := FALSE);
END_IF

timer(IN := TRUE, PT := T#500ms);
GVL.motorCommandWithinTimeout := NOT timer.Q;
