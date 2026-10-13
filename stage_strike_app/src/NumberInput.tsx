import {Minus, Plus} from "lucide-react";
import {Button} from "@/components/ui/button";
import {ButtonGroup} from "@/components/ui/button-group";
import {Input} from "@/components/ui/input";
import {cn} from "@/lib/utils";

export interface NumberInputProps {
    id?: string;
    value: number;
    min?: number;
    max?: number;
    onChange: (oldVal: number, newVal: number) => void;
    className?: string;
}

/** A number with - and + buttons either side */
export function NumberInput({id, value, min, max, onChange, className}: NumberInputProps) {
    const lowest = min ?? Number.MIN_SAFE_INTEGER;
    const highest = max ?? Number.MAX_SAFE_INTEGER;

    return (
        <ButtonGroup className={className}>
            <Button
                variant="outline"
                size="icon"
                aria-label="-"
                disabled={value <= lowest}
                onClick={() => onChange(value, Math.max(lowest, value - 1))}
            >
                <Minus/>
            </Button>
            <Input
                id={id}
                type="number"
                inputMode="numeric"
                min={min}
                max={max}
                value={value}
                onChange={(e) => onChange(value, Number.parseInt(e.target.value))}
                className={cn(
                    "w-16 text-center tabular-nums",
                    "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
                )}
            />
            <Button
                variant="outline"
                size="icon"
                aria-label="+"
                disabled={value >= highest}
                onClick={() => onChange(value, Math.min(highest, value + 1))}
            >
                <Plus/>
            </Button>
        </ButtonGroup>
    );
}
