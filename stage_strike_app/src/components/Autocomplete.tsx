import {type ReactNode, useEffect, useMemo, useState} from "react";
import {Command, CommandItem, CommandList} from "@/components/ui/command";
import {Input} from "@/components/ui/input";
import {cn} from "@/lib/utils";

interface AutocompleteProps<T> {
  id?: string;
  options: T[];
  // The option picked
  value: T | null;
  getLabel: (option: T) => string;
  getKey: (option: T) => string;
  renderOption?: (option: T) => ReactNode;
  // Shown inside the input, before the text (e.g. a flag)
  startAdornment?: ReactNode;
  onSelect: (option: T | null) => void;
  // With freeSolo, any text is a value: the input shows inputValue and
  // reports what's typed. Otherwise the text only searches the options.
  freeSolo?: boolean;
  inputValue?: string;
  onInputChange?: (text: string) => void;
  // Typed characters before options show
  minChars?: number;
  limit?: number;
  placeholder?: string;
  disabled?: boolean;
  onBlur?: () => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  className?: string;
}

/**
 * A text input suggesting options as it's typed in, picked with a tap or
 * the arrow keys and Enter.
 */
export function Autocomplete<T>({
  id,
  options,
  value,
  getLabel,
  getKey,
  renderOption,
  startAdornment,
  onSelect,
  freeSolo = false,
  inputValue,
  onInputChange,
  minChars = 0,
  limit = 50,
  placeholder,
  disabled,
  onBlur,
  onKeyDown,
  className,
}: AutocompleteProps<T>) {
  const selectedLabel = value != null ? getLabel(value) : "";
  const [text, setText] = useState(selectedLabel);
  // Whether the text was typed, so it filters the options
  const [typed, setTyped] = useState(false);
  const [focused, setFocused] = useState(false);

  const shown = freeSolo ? (inputValue ?? "") : text;

  useEffect(() => {
    if (!focused) {
      setText(selectedLabel);
      setTyped(false);
    }
  }, [selectedLabel, focused]);

  const query = typed ? shown.trim().toLocaleLowerCase() : "";
  const filtered = useMemo(() => {
    if (query.length < minChars) return [];
    return options
      .filter((o) => !query || getLabel(o).toLocaleLowerCase().includes(query))
      .slice(0, limit);
  }, [options, query, minChars, limit, getLabel]);

  const open = focused && !disabled && filtered.length > 0;

  const pick = (option: T) => {
    setText(getLabel(option));
    setTyped(false);
    onSelect(option);
  };

  return <Command shouldFilter={false} className={cn("relative overflow-visible bg-transparent", className)}>
    <div className="relative">
      {startAdornment &&
        <span className="pointer-events-none absolute top-1/2 left-2.5 flex -translate-y-1/2 items-center">
          {startAdornment}
        </span>
      }
      <Input
        id={id}
        value={shown}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        className={cn(startAdornment && "pl-10")}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false);
          if (!freeSolo && text !== selectedLabel) {
            // Cleared: no option. Anything else typed goes back to the option
            if (text.trim() === "") onSelect(null);
            else setText(selectedLabel);
          }
          setTyped(false);
          onBlur?.();
        }}
        onChange={(e) => {
          setTyped(true);
          if (freeSolo) onInputChange?.(e.target.value);
          else setText(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") setTyped(false);
          onKeyDown?.(e);
        }}
      />
    </div>
    {open &&
      <CommandList
        className="absolute top-full z-50 mt-1 w-full min-w-48 rounded-md border bg-popover p-1 shadow-md"
        // Keeps the focus in the input
        onMouseDown={(e) => e.preventDefault()}
      >
        {filtered.map((option) =>
          <CommandItem key={getKey(option)} value={getKey(option)} onSelect={() => pick(option)}>
            {renderOption ? renderOption(option) : getLabel(option)}
          </CommandItem>
        )}
      </CommandList>
    }
  </Command>;
}
