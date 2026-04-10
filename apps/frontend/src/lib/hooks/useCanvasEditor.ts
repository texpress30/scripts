"use client";

import { useState, useCallback } from "react";
import type { FabricObject } from "fabric";

export interface CanvasEditorState {
  canvasWidth: number;
  canvasHeight: number;
  backgroundColor: string;
  selectedObject: FabricObject | null;
  hasUnsavedChanges: boolean;
}

export function useCanvasEditor(initialWidth = 1080, initialHeight = 1080, initialBg = "#FFFFFF") {
  const [canvasWidth, setCanvasWidth] = useState(initialWidth);
  const [canvasHeight, setCanvasHeight] = useState(initialHeight);
  const [backgroundColor, setBackgroundColor] = useState(initialBg);
  const [selectedObject, setSelectedObject] = useState<FabricObject | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const markDirty = useCallback(() => setHasUnsavedChanges(true), []);
  const markClean = useCallback(() => setHasUnsavedChanges(false), []);

  const updateCanvasSize = useCallback((width: number, height: number) => {
    setCanvasWidth(width);
    setCanvasHeight(height);
    setHasUnsavedChanges(true);
  }, []);

  const updateBackgroundColor = useCallback((color: string) => {
    setBackgroundColor(color);
    setHasUnsavedChanges(true);
  }, []);

  return {
    canvasWidth,
    canvasHeight,
    backgroundColor,
    selectedObject,
    hasUnsavedChanges,
    setSelectedObject,
    updateCanvasSize,
    updateBackgroundColor,
    markDirty,
    markClean,
  };
}
