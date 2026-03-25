(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION_BLOCK PC_STATE_RECV
VAR_INPUT
    channel : ifmDevice.CAN_CHANNEL;
END_VAR
VAR
    rx     : ifmRCAN.CAN_Rx;
    timer  : TON;
    rxData : ARRAY[0..7] OF USINT;
END_VAR

rx(xEnable := TRUE, eChannel := channel, xExtended := TRUE, udiID := 16#00000300);

IF rx.uiAvailable > 0 AND rx.usiDLC = 1 THEN
    rxData := rx.aData;
    GVL.driveMode := TO_DriveMode(CAN_EXTRACT_BITS(rxData, 0, 2, FALSE));
    timer(IN := FALSE);
END_IF

timer(IN := TRUE, PT := T#1000ms);
GVL.pcStateWithinTimeout := NOT timer.Q;
