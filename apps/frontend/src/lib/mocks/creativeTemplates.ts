import type { CreativeTemplate } from "@/lib/types/creative-studio";

export const mockCreativeTemplates: CreativeTemplate[] = [
  {
    id: "tpl_001",
    subaccount_id: 1,
    name: "Summer Sale Banner",
    canvas_width: 1080,
    canvas_height: 1080,
    background_color: "#FFF3E0",
    elements: [
      { type: "text", position_x: 40, position_y: 60, width: 1000, height: 80, style: { fontSize: 48, fontWeight: "bold", color: "#E65100" }, dynamic_binding: null, content: "SUMMER SALE" },
      { type: "dynamic_field", position_x: 40, position_y: 200, width: 1000, height: 60, style: { fontSize: 32, color: "#333" }, dynamic_binding: "{{product_title}}", content: "" },
      { type: "dynamic_field", position_x: 40, position_y: 900, width: 300, height: 60, style: { fontSize: 36, fontWeight: "bold", color: "#E65100" }, dynamic_binding: "{{price}}", content: "" },
      { type: "image", position_x: 200, position_y: 300, width: 680, height: 500, style: {}, dynamic_binding: "{{image_url}}", content: "" },
    ],
    created_at: "2026-03-20T10:00:00Z",
    updated_at: "2026-03-28T14:30:00Z",
  },
  {
    id: "tpl_002",
    subaccount_id: 1,
    name: "Product Showcase — Wide",
    canvas_width: 1200,
    canvas_height: 628,
    background_color: "#FFFFFF",
    elements: [
      { type: "dynamic_field", position_x: 640, position_y: 40, width: 520, height: 50, style: { fontSize: 28, fontWeight: "bold", color: "#111" }, dynamic_binding: "{{product_title}}", content: "" },
      { type: "dynamic_field", position_x: 640, position_y: 110, width: 520, height: 40, style: { fontSize: 20, color: "#666" }, dynamic_binding: "{{description}}", content: "" },
      { type: "image", position_x: 20, position_y: 20, width: 580, height: 588, style: {}, dynamic_binding: "{{image_url}}", content: "" },
    ],
    created_at: "2026-03-25T08:15:00Z",
    updated_at: "2026-03-25T08:15:00Z",
  },
  {
    id: "tpl_003",
    subaccount_id: 1,
    name: "Instagram Story Ad",
    canvas_width: 1080,
    canvas_height: 1920,
    background_color: "#1A1A2E",
    elements: [
      { type: "text", position_x: 40, position_y: 100, width: 1000, height: 60, style: { fontSize: 40, fontWeight: "bold", color: "#E94560" }, dynamic_binding: null, content: "NEW ARRIVAL" },
      { type: "dynamic_field", position_x: 40, position_y: 1700, width: 1000, height: 50, style: { fontSize: 28, color: "#FFFFFF" }, dynamic_binding: "{{product_title}}", content: "" },
    ],
    created_at: "2026-03-30T16:45:00Z",
    updated_at: "2026-04-01T09:00:00Z",
  },
];
