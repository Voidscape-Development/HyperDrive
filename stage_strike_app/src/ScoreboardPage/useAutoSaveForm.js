import React from "react";

/**
 * Form state that follows HyperDrive and saves itself.
 *
 * The fields start from, and keep following, `serverValues` (what HyperDrive has),
 * except for the ones edited here that haven't been saved yet, so an update
 * coming back from HyperDrive never overwrites what someone is typing.
 *
 * Edits are saved `debounceMs` after the last one, or right away with
 * `flush()` (on blur / Enter) or `setField(..., {immediate: true})`.
 * `save(values, changedFields)` must return a promise; if it fails the fields
 * stay unsaved and are sent again with the next save.
 *
 * @template T
 * @param {T} serverValues
 * @param {(values: T, changed: string[]) => Promise<any>} save
 * @param {number} debounceMs
 */
export function useAutoSaveForm(serverValues, save, debounceMs = 1200) {
    const valuesRef = React.useRef(serverValues);
    const [values, setValues] = React.useState(serverValues);

    // field -> edit number; a field is cleared once that edit is saved
    const dirty = React.useRef({});
    const edits = React.useRef(0);
    const timer = React.useRef(null);
    const saveRef = React.useRef(save);
    saveRef.current = save;

    const serverKey = JSON.stringify(serverValues);
    React.useEffect(() => {
        const next = {...valuesRef.current};
        let changed = false;
        for (const key in serverValues) {
            if (!(key in dirty.current) && JSON.stringify(next[key]) !== JSON.stringify(serverValues[key])) {
                next[key] = serverValues[key];
                changed = true;
            }
        }
        if (changed) {
            valuesRef.current = next;
            setValues(next);
        }
    }, [serverKey]); // eslint-disable-line react-hooks/exhaustive-deps

    const flush = React.useCallback(() => {
        clearTimeout(timer.current);
        timer.current = null;
        const sending = {...dirty.current};
        const fields = Object.keys(sending);
        if (fields.length === 0) {
            return Promise.resolve();
        }
        return Promise.resolve(saveRef.current(valuesRef.current, fields)).then(() => {
            for (const key of fields) {
                // Only if it wasn't edited again while this was being sent
                if (dirty.current[key] === sending[key]) {
                    delete dirty.current[key];
                }
            }
        }).catch(() => {});
    }, []);

    const setField = React.useCallback((key, value, {immediate = false} = {}) => {
        edits.current += 1;
        dirty.current[key] = edits.current;
        valuesRef.current = {...valuesRef.current, [key]: value};
        setValues(valuesRef.current);

        clearTimeout(timer.current);
        if (immediate) {
            flush();
        } else {
            timer.current = setTimeout(flush, debounceMs);
        }
    }, [flush, debounceMs]);

    // Anything still waiting is sent when the form goes away
    React.useEffect(() => () => {
        if (timer.current) {
            flush();
        }
    }, [flush]);

    return {values, setField, flush};
}

/** Props for a text field so it saves when it loses focus or Enter is pressed. */
export const saveOnCommit = (flush) => ({
    onBlur: flush,
    onKeyDown: (e) => {
        if (e.key === 'Enter') {
            flush();
        }
    },
});
