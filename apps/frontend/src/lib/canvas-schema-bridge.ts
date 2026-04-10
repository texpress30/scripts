/**
 * Schema bridge between Fabric.js canvas objects and backend CanvasElement format.
 *
 * Backend CanvasElement:
 *   type: "text" | "image" | "shape" | "dynamic_field"
 *   position_x, position_y, width, height
 *   style: { color, font_size, fill_color, shape_type }
 *   dynamic_binding: "{{field_name}}" | null
 *   content: string
 *
 * This module converts between Fabric.js serialized objects and CanvasElement[].
 */

import type { CanvasElement } from "@/lib/hooks/useCreativeTemplates";

interface FabricObjectJSON {
  type: string;
  left: number;
  top: number;
  width: number;
  height: number;
  scaleX?: number;
  scaleY?: number;
  fill?: string;
  text?: string;
  fontSize?: number;
  fontFamily?: string;
  src?: string;
  rx?: number;
  ry?: number;
  radius?: number;
  // Custom data stored on the fabric object
  data?: {
    elementType?: string;
    dynamicBinding?: string;
    shapeType?: string;
  };
  [key: string]: unknown;
}

interface FabricCanvasJSON {
  version: string;
  objects: FabricObjectJSON[];
}

/**
 * Convert Fabric.js canvas JSON export to backend CanvasElement array.
 */
export function fabricToCanvasElements(fabricJSON: FabricCanvasJSON): CanvasElement[] {
  return (fabricJSON.objects || []).map((obj) => {
    const scaleX = obj.scaleX ?? 1;
    const scaleY = obj.scaleY ?? 1;
    const elementType = obj.data?.elementType || inferElementType(obj);
    const width = (obj.width || 0) * scaleX;
    const height = (obj.height || 0) * scaleY;

    const base: CanvasElement = {
      type: elementType as CanvasElement["type"],
      position_x: obj.left || 0,
      position_y: obj.top || 0,
      width,
      height,
      style: {},
      dynamic_binding: null,
      content: "",
    };

    switch (elementType) {
      case "text":
        base.content = obj.text || "";
        base.style = {
          color: typeof obj.fill === "string" ? obj.fill : "#000000",
          font_size: obj.fontSize || 16,
          font_family: obj.fontFamily || "Arial",
        };
        break;

      case "dynamic_field":
        base.dynamic_binding = obj.data?.dynamicBinding || obj.text || "";
        base.content = obj.text || "";
        base.style = {
          color: typeof obj.fill === "string" ? obj.fill : "#000000",
          font_size: obj.fontSize || 16,
          font_family: obj.fontFamily || "Arial",
        };
        break;

      case "image":
        base.content = obj.src || "";
        if (obj.data?.dynamicBinding) {
          base.dynamic_binding = obj.data.dynamicBinding;
        }
        break;

      case "shape": {
        const shapeType = obj.data?.shapeType || (obj.type === "circle" || obj.rx ? "ellipse" : "rectangle");
        base.style = {
          fill_color: typeof obj.fill === "string" ? obj.fill : "#CCCCCC",
          shape_type: shapeType,
        };
        base.content = shapeType;
        if (obj.type === "circle" || obj.type === "ellipse") {
          base.width = (obj.radius || obj.rx || obj.width || 0) * 2 * scaleX;
          base.height = (obj.radius || obj.ry || obj.height || 0) * 2 * scaleY;
        }
        break;
      }
    }

    return base;
  });
}

/**
 * Convert backend CanvasElement array to Fabric.js-loadable objects.
 * Returns object descriptors that can be used with fabric.js constructors.
 */
export function canvasElementsToFabricObjects(elements: CanvasElement[]): Record<string, unknown>[] {
  return elements.map((el): Record<string, unknown> => {
    switch (el.type) {
      case "text":
        return {
          type: "textbox",
          left: el.position_x,
          top: el.position_y,
          width: el.width || 200,
          height: el.height || 40,
          text: el.content || "Text",
          fill: (el.style.color as string) || "#000000",
          fontSize: (el.style.font_size as number) || 16,
          fontFamily: (el.style.font_family as string) || "Arial",
          data: { elementType: "text" },
        };

      case "dynamic_field":
        return {
          type: "textbox",
          left: el.position_x,
          top: el.position_y,
          width: el.width || 200,
          height: el.height || 40,
          text: el.dynamic_binding || el.content || "{{field}}",
          fill: (el.style.color as string) || "#6366f1",
          fontSize: (el.style.font_size as number) || 16,
          fontFamily: (el.style.font_family as string) || "Arial",
          data: {
            elementType: "dynamic_field",
            dynamicBinding: el.dynamic_binding || "",
          },
        };

      case "image":
        return {
          type: "image",
          left: el.position_x,
          top: el.position_y,
          width: el.width || 200,
          height: el.height || 200,
          src: el.content || "",
          data: {
            elementType: "image",
            dynamicBinding: el.dynamic_binding || undefined,
          },
        };

      case "shape": {
        const shapeType = (el.style.shape_type as string) || el.content || "rectangle";
        const fill = (el.style.fill_color as string) || "#CCCCCC";
        if (shapeType === "ellipse" || shapeType === "circle") {
          return {
            type: "ellipse",
            left: el.position_x,
            top: el.position_y,
            rx: (el.width || 100) / 2,
            ry: (el.height || 100) / 2,
            fill,
            data: { elementType: "shape", shapeType: "ellipse" },
          };
        }
        return {
          type: "rect",
          left: el.position_x,
          top: el.position_y,
          width: el.width || 200,
          height: el.height || 100,
          fill,
          data: { elementType: "shape", shapeType: "rectangle" },
        };
      }

      default:
        return {
          type: "rect",
          left: el.position_x,
          top: el.position_y,
          width: el.width || 100,
          height: el.height || 100,
          fill: "#CCCCCC",
          data: { elementType: "shape", shapeType: "rectangle" },
        };
    }
  });
}

function inferElementType(obj: FabricObjectJSON): string {
  if (obj.data?.elementType) return obj.data.elementType;
  if (obj.type === "textbox" || obj.type === "i-text" || obj.type === "text") {
    if (obj.data?.dynamicBinding) return "dynamic_field";
    return "text";
  }
  if (obj.type === "image") return "image";
  if (obj.type === "rect" || obj.type === "circle" || obj.type === "ellipse") return "shape";
  return "shape";
}
