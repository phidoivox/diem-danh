"use client";

export { getClientFaceDetector, closeClientFaceDetector, matchServerIdentities } from "./face-detector";
export type { LocalFaceBox } from "./face-detector";
export { stabilizeDecisions, filterFreshChecked, boxColor, boxLabel } from "./kiosk-decisions";
export type { StableEntry } from "./kiosk-decisions";
export { default as KioskPage } from "./kiosk-page";
