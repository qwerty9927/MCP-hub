"use client";

import React, { useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
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
    disabled?: boolean;
}

export function SchemaForm({ schema, values, onChange, disabled }: SchemaFormProps) {
    const properties = schema?.properties || {};
    const requiredList: string[] = schema?.required || [];
    const entries = Object.entries(properties);

    if (entries.length === 0) {
        return (
            <div className="rounded-lg border border-border p-4 text-center text-sm text-muted-foreground bg-muted/20">
                This tool does not define any input parameters. You can execute it directly.
            </div>
        );
    }

    const handleFieldChange = (key: string, val: any) => {
        onChange({
            ...values,
            [key]: val,
        });
    };

    return (
        <div className="space-y-4">
            {entries.map(([key, prop]: [string, any]) => {
                const isRequired = requiredList.includes(key);
                const propType = prop.type || "string";
                const currentVal = values[key];

                return (
                    <div
                        key={key}
                        className="space-y-1.5 rounded-lg border border-border/60 bg-muted/10 p-3"
                    >
                        <div className="flex items-center justify-between">
                            <Label htmlFor={`field-${key}`} className="font-mono text-sm">
                                {key}
                                {isRequired && <span className="text-destructive ml-1">*</span>}
                            </Label>
                            <span className="text-[11px] font-mono text-muted-foreground">
                                {propType}
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
                                    <SelectValue placeholder={`Select ${key}...`} />
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
                                <span className="text-xs text-muted-foreground">
                                    {currentVal ? "True" : "False"}
                                </span>
                            </div>
                        ) : propType === "number" || propType === "integer" ? (
                            <Input
                                id={`field-${key}`}
                                type="number"
                                step={propType === "integer" ? "1" : "any"}
                                placeholder={
                                    prop.default !== undefined ? String(prop.default) : "0"
                                }
                                value={currentVal !== undefined ? currentVal : ""}
                                onChange={(e) =>
                                    handleFieldChange(
                                        key,
                                        e.target.value === "" ? undefined : Number(e.target.value)
                                    )
                                }
                                disabled={disabled}
                                className="h-9 font-mono text-sm"
                            />
                        ) : propType === "array" ? (
                            <Textarea
                                id={`field-${key}`}
                                placeholder={`["item1", "item2"]`}
                                value={
                                    typeof currentVal === "object"
                                        ? JSON.stringify(currentVal)
                                        : currentVal || ""
                                }
                                onChange={(e) => {
                                    try {
                                        const parsed = JSON.parse(e.target.value);
                                        handleFieldChange(key, parsed);
                                    } catch {
                                        handleFieldChange(key, e.target.value);
                                    }
                                }}
                                disabled={disabled}
                                rows={2}
                                className="font-mono text-xs"
                            />
                        ) : propType === "object" ? (
                            <Textarea
                                id={`field-${key}`}
                                placeholder={`{"key": "value"}`}
                                value={
                                    typeof currentVal === "object"
                                        ? JSON.stringify(currentVal, null, 2)
                                        : currentVal || ""
                                }
                                onChange={(e) => {
                                    try {
                                        const parsed = JSON.parse(e.target.value);
                                        handleFieldChange(key, parsed);
                                    } catch {
                                        handleFieldChange(key, e.target.value);
                                    }
                                }}
                                disabled={disabled}
                                rows={3}
                                className="font-mono text-xs"
                            />
                        ) : (
                            <Input
                                id={`field-${key}`}
                                type="text"
                                placeholder={
                                    prop.default !== undefined
                                        ? String(prop.default)
                                        : `Enter ${key}...`
                                }
                                value={currentVal !== undefined ? currentVal : ""}
                                onChange={(e) => handleFieldChange(key, e.target.value)}
                                disabled={disabled}
                                className="h-9 text-sm"
                            />
                        )}
                    </div>
                );
            })}
        </div>
    );
}
