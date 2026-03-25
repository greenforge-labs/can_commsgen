(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION_BLOCK DRIVE_STATUS_SEND
VAR_INPUT
    channel            : ifmDevice.CAN_CHANNEL;
    actualVelocity_rpm : REAL;
    motorTemp_degC     : REAL;
    busVoltage_V       : REAL;
    faultCode          : USINT;
END_VAR
VAR
    tx   : ifmRCAN.CAN_Tx;
    data : ARRAY[0..7] OF USINT;
END_VAR

data := [8(0)];
CAN_INSERT_BITS(TO_LINT(REAL_TO_INT(actualVelocity_rpm / 0.1)),  0,  16, data);
CAN_INSERT_BITS(TO_LINT(REAL_TO_INT(motorTemp_degC / 0.1)),       16, 12, data);
CAN_INSERT_BITS(TO_LINT(REAL_TO_UINT(busVoltage_V / 0.1)),        28, 10, data);
CAN_INSERT_BITS(TO_LINT(faultCode),                                38, 8,  data);

tx(xEnable := TRUE, eChannel := channel, xExtended := TRUE,
   udiID := 16#00000200, usiDLC := 6, aData := data);
