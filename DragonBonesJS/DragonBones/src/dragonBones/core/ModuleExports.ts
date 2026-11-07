/**
 * The MIT License (MIT)
 *
 * Copyright (c) 2012-2025 DragonBones team and other contributors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
// Keep the module adapter last in the outFile bundle. Every public
// namespace member must be initialized before exports-only loaders copy it.
declare var exports: any;
declare var module: any;
declare var define: any;
// DragonBones.ts already declares 'global' for the browser fallback.
// Do not redeclare it here: ambient types can conflict with that variable.
if (typeof exports === "object" && typeof module === "object") {
    module.exports = dragonBones;
}
else if (typeof define === "function" && define["amd"]) {
    // Register the library itself; do not require "dragonBones" from within
    // its own AMD module (that creates a circular dependency).
    define([], function () { return dragonBones; });
}
else if (typeof exports === "object") {
    // Assign exported members to the supplied exports object instead of
    // rebinding the local variable (which callers cannot observe).
    for (const key of Object.keys(dragonBones)) {
        exports[key] = (dragonBones as any)[key];
    }
}
else if (typeof global !== "undefined") {
    global.dragonBones = dragonBones;
}
