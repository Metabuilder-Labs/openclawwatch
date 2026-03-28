"use strict";
/**
 * Core types for the OCW TypeScript SDK.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SpanStatus = exports.SpanKind = void 0;
var SpanKind;
(function (SpanKind) {
    SpanKind["INTERNAL"] = "internal";
    SpanKind["CLIENT"] = "client";
    SpanKind["SERVER"] = "server";
    SpanKind["PRODUCER"] = "producer";
    SpanKind["CONSUMER"] = "consumer";
})(SpanKind || (exports.SpanKind = SpanKind = {}));
var SpanStatus;
(function (SpanStatus) {
    SpanStatus["OK"] = "ok";
    SpanStatus["ERROR"] = "error";
    SpanStatus["UNSET"] = "unset";
})(SpanStatus || (exports.SpanStatus = SpanStatus = {}));
//# sourceMappingURL=types.js.map