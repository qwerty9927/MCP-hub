"use client";

import React, { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { RotateCcw } from "lucide-react";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

interface SchemaFormProps {
    schema: Record<string, any>;
    values: Record<string, any>;
    onChange: (vals: Record<string, any>) => void;
    errors?: Record<string, string>;
    disabled?: boolean;
}

export function SchemaForm({ schema, values, onChange, errors = {}, disabled }: SchemaFormProps) {
    const properties = schema?.properties || {};
    const requiredList: string[] = schema?.required || [];
    const entries = Object.entries(properties);

    // Local string buffer for complex fields (objects/arrays) to avoid reformatting on every keystroke
    const [rawComplexInputs, setRawComplexInputs] = useState<Record<string, string>>({});

    // Keep raw complex inputs synced when values change externally
    useEffect(() => {
        const nextRaw: Record<string, string> = {};
        for (const [key, prop] of entries) {
            const propType = (prop as any)?.type;
            if (propType === "array" || propType === "object") {
                if (values[key] !== undefined) {
                    nextRaw[key] =
                        typeof values[key] === "object"
                            ? JSON.stringify(values[key], null, 2)
                            : String(values[key]);
                }
            }
        }
        setRawComplexInputs((prev) => ({ ...nextRaw, ...prev }));
    }, [schema]);

    if (entries.length === 0) {
        return (
            <div className="rounded-lg border border-border p-4 text-center text-sm text-muted-foreground bg-muted/20">
                This tool does not define any input parameters. You can execute it directly.
            </div>
        );
    }

    const handleFieldChange = (key: string, val: any) => {
        const next = { ...values };
        if (val === undefined || val === "") {
            delete next[key];
        } else {
            next[key] = val;
        }
        onChange(next);
    };

    const handleResetDefaults = () => {
        const defaults: Record<string, any> = {};
        for (const [k, v] of Object.entries<any>(properties)) {
            if (v.default !== undefined) {
                defaults[k] = v.default;
            }
        }
        onChange(defaults);
        const resetRaw: Record<string, string> = {};
        for (const [k, v] of Object.entries(defaults)) {
            if (typeof v === "object") {
                resetRaw[k] = JSON.stringify(v, null, 2);
            }
        }
        setRawComplexInputs(resetRaw);
    };

    const hasAnyDefaults = entries.some(([_, p]: [string, any]) => p.default !== undefined);

    return (
        <div className="space-y-4">
            {hasAnyDefaults && (
                <div className="flex justify-end">
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={handleResetDefaults}
                        disabled={disabled}
                        className="h-7 text-xs text-muted-foreground gap-1.5"
                    >
                        <RotateCcw className="h-3 w-3" />
                        Reset to Defaults
                    </Button>
                </div>
            )}

            {entries.map(([key, prop]: [string, any]) => {
                const isRequired = requiredList.includes(key);
                const propType = prop.type || "string";
                const currentVal = values[key];
                const fieldError = errors[key];

                return (
                    <div
                        key={key}
                        className={`space-y-1.5 rounded-lg border p-3 transition-colors ${
                            fieldError
                                ? "border-destructive/60 bg-destructive/5"
                                : "border-border/60 bg-muted/10"
                        }`}
                    >
                        <div className="flex items-center justify-between">
                            <Label
                                htmlFor={`field-${key}`}
                                className="font-mono text-sm flex items-center gap-1"
                            >
                                <span>{key}</span>
                                {isRequired && (
                                    <span
                                        className="text-destructive font-semibold"
                                        title="Required field"
                                    >
                                        *
                                    </span>
                                )}
                            </Label>
                            <span className="text-[11px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                {propType}
                                {prop.format ? ` (${prop.format})` : ""}
                            </span>
                        </div>

                        {prop.description && (
                            <p className="text-xs text-muted-foreground">{prop.description}</p>
                        )}

                        {/* Enum Select */}
                        {prop.enum ? (
                            <Select
                                value={currentVal !== undefined ? String(currentVal) : ""}
                                onValueChange={(v) => handleFieldChange(key, v)}
                                disabled={disabled}
                            >
                                <SelectTrigger id={`field-${key}`} className="h-9">
                                    <SelectValue
                                        placeholder={
                                            prop.default !== undefined
                                                ? `Default: ${prop.default}`
                                                : `Select ${key}...`
                                        }
                                    />
                                </SelectTrigger>
                                <SelectContent>
                                    {prop.enum.map((opt: any) => (
                                        <SelectItem key={String(opt)} value={String(opt)}>
                                            {String(opt)}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        ) : propType === "boolean" ? (
                            <div className="flex items-center gap-2 pt-1">
                                <Switch
                                    id={`field-${key}`}
                                    checked={Boolean(currentVal)}
                                    onCheckedChange={(checked) => handleFieldChange(key, checked)}
                                    disabled={disabled}
                                />
                                <span className="text-xs text-muted-foreground font-mono">
                                    {currentVal ? "true" : "false"}
                                </span>
                            </div>
                        ) : propType === "number" || propType === "integer" ? (
                            <Input
                                id={`field-${key}`}
                                type="number"
                                step={propType === "integer" ? "1" : "any"}
                                min={prop.minimum}
                                max={prop.maximum}
                                placeholder={
                                    prop.default !== undefined
                                        ? `Default: ${prop.default}`
                                        : "Enter number..."
                                }
                                value={currentVal !== undefined ? currentVal : ""}
                                onChange={(e) => {
                                    const val = e.target.value;
                                    if (val === "") {
                                        handleFieldChange(key, undefined);
                                    } else {
                                        const num =
                                            propType === "integer"
                                                ? parseInt(val, 10)
                                                : parseFloat(val);
                                        handleFieldChange(key, isNaN(num) ? undefined : num);
                                    }
                                }}
                                disabled={disabled}
                                className="h-9 font-mono text-sm"
                            />
                        ) : propType === "array" ? (
                            <div className="space-y-1">
                                <Textarea
                                    id={`field-${key}`}
                                    placeholder={
                                        prop.default !== undefined
                                            ? JSON.stringify(prop.default)
                                            : '["item1", "item2"]'
                                    }
                                    value={
                                        rawComplexInputs[key] ??
                                        (typeof currentVal === "object"
                                            ? JSON.stringify(currentVal, null, 2)
                                            : currentVal || "")
                                    }
                                    onChange={(e) => {
                                        const text = e.target.value;
                                        setRawComplexInputs((prev) => ({
                                            ...prev,
                                            [key]: text,
                                        }));
                                        try {
                                            const parsed = JSON.parse(text);
                                            handleFieldChange(key, parsed);
                                        } catch {
                                            // Keep raw string in formValues if valid string or user typing
                                            handleFieldChange(key, text);
                                        }
                                    }}
                                    disabled={disabled}
                                    rows={2}
                                    className="font-mono text-xs"
                                />
                                <span className="text-[11px] text-muted-foreground">
                                    Format: JSON array, e.g. ["val1", "val2"]
                                </span>
                            </div>
                        ) : propType === "object" ? (
                            <div className="space-y-1">
                                <Textarea
                                    id={`field-${key}`}
                                    placeholder={
                                        prop.default !== undefined
                                            ? JSON.stringify(prop.default, null, 2)
                                            : '{\n  "key": "value"\n}'
                                    }
                                    value={
                                        rawComplexInputs[key] ??
                                        (typeof currentVal === "object"
                                            ? JSON.stringify(currentVal, null, 2)
                                            : currentVal || "")
                                    }
                                    onChange={(e) => {
                                        const text = e.target.value;
                                        setRawComplexInputs((prev) => ({
                                            ...prev,
                                            [key]: text,
                                        }));
                                        try {
                                            const parsed = JSON.parse(text);
                                            handleFieldChange(key, parsed);
                                        } catch {
                                            handleFieldChange(key, text);
                                        }
                                    }}
                                    disabled={disabled}
                                    rows={3}
                                    className="font-mono text-xs"
                                />
                                <span className="text-[11px] text-muted-foreground">
                                    Format: JSON object, e.g. {"{"}"key": "value"{"}"}
                                </span>
                            </div>
                        ) : (
                            <Input
                                id={`field-${key}`}
                                type="text"
                                placeholder={
                                    prop.default !== undefined
                                        ? `Default: ${prop.default}`
                                        : `Enter ${key}...`
                                }
                                value={currentVal !== undefined ? currentVal : ""}
                                onChange={(e) => handleFieldChange(key, e.target.value)}
                                disabled={disabled}
                                className="h-9 text-sm"
                            />
                        )}

                        {fieldError && (
                            <p className="text-xs font-medium text-destructive mt-1">
                                {fieldError}
                            </p>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
