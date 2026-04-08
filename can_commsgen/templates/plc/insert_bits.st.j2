(* THIS FILE IS AUTO-GENERATED. DO NOT EDIT. *)
FUNCTION CAN_INSERT_BITS : BOOL
VAR_INPUT
    value     : LINT;
    bitOffset : UINT;
    bitCount  : UINT;
END_VAR
VAR_IN_OUT
    data      : ARRAY[0..7] OF USINT;
END_VAR
VAR
    i       : UINT;
    byteIdx : UINT;
    bitIdx  : UINT;
    raw     : ULINT;
END_VAR

// --- BEGIN IMPLEMENTATION ---

raw := LINT_TO_ULINT(value);
FOR i := 0 TO bitCount - 1 DO
    byteIdx := (bitOffset + i) / 8;
    bitIdx  := (bitOffset + i) MOD 8;
    IF (raw AND SHL(ULINT#1, i)) <> 0 THEN
        data[byteIdx] := data[byteIdx] OR SHL(USINT#1, bitIdx);
    ELSE
        data[byteIdx] := data[byteIdx] AND NOT SHL(USINT#1, bitIdx);
    END_IF
END_FOR

CAN_INSERT_BITS := TRUE;
