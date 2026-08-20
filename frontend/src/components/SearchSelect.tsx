"use client";

import * as Popover from "@radix-ui/react-popover";
import { Command } from "cmdk";
import { useId, useState } from "react";

export interface SearchSelectOption {
  value: string;
  label: string;
}

interface SearchSelectProps {
  label: string;
  value: string;
  options: SearchSelectOption[];
  onValueChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
}

function SearchIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true" className="search-select__icon"><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></svg>;
}

function ChevronDownIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true" className="search-select__icon"><path d="m6 9 6 6 6-6" /></svg>;
}

export default function SearchSelect({ label, value, options, onValueChange, placeholder, disabled = false }: SearchSelectProps) {
  const [open, setOpen] = useState(false);
  const listboxId = useId();
  const selected = options.find((option) => option.value === value);
  const displayLabel = selected?.label || value || placeholder;

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button type="button" className="search-select__trigger" aria-label={label} aria-controls={listboxId} aria-expanded={open} disabled={disabled}>
          <span>{displayLabel}</span>
          <ChevronDownIcon />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="search-select__popover" align="start" sideOffset={6} collisionPadding={12}>
          <Command shouldFilter label={label}>
            <div className="search-select__search-field">
              <SearchIcon />
              <Command.Input autoFocus className="search-select__input" placeholder={`Cari ${label.toLocaleLowerCase("id-ID")}...`} />
            </div>
            <Command.List id={listboxId} className="search-select__options">
              <Command.Empty className="search-select__empty">Tidak ada pilihan yang cocok.</Command.Empty>
              <Command.Group>
                {options.map((option) => (
                  <Command.Item
                    key={option.value}
                    value={option.label}
                    className="search-select__option"
                    data-selected={option.value === value || undefined}
                    onSelect={() => { onValueChange(option.value); setOpen(false); }}
                  >
                    {option.label}
                  </Command.Item>
                ))}
              </Command.Group>
            </Command.List>
          </Command>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
