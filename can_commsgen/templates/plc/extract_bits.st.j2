(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION CAN_EXTRACT_BITS : LINT
VAR_INPUT
    data      : ARRAY[0..7] OF USINT;
    bitOffset : UINT;
    bitCount  : UINT;
    signed    : BOOL;
END_VAR
VAR
    i       : UINT;
    byteIdx : UINT;
    bitIdx  : UINT;
    raw     : ULINT;
END_VAR

raw := 0;
FOR i := 0 TO bitCount - 1 DO
    byteIdx := (bitOffset + i) / 8;
    bitIdx  := (bitOffset + i) MOD 8;
    IF (data[byteIdx] AND SHL(USINT#1, bitIdx)) <> 0 THEN
        raw := raw OR SHL(ULINT#1, i);
    END_IF
END_FOR

IF signed AND (raw AND SHL(ULINT#1, bitCount - 1)) <> 0 THEN
    raw := raw OR NOT (SHL(ULINT#1, bitCount) - 1);
END_IF

CAN_EXTRACT_BITS := ULINT_TO_LINT(raw);
