export type CanvasElementType = "text" | "image" | "shape" | "dynamic_field";

export type CanvasElement = {
  type: CanvasElementType;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  style: Record<string, unknown>;
  dynamic_binding: string | null;
  content: string;
};

export type CreativeTemplate = {
  id: string;
  subaccount_id: number;
  name: string;
  canvas_width: number;
  canvas_height: number;
  elements: CanvasElement[];
  background_color: string;
  created_at: string;
  updated_at: string;
};

export type CreativeTemplatesResponse = {
  items: CreativeTemplate[];
};

export type CreateTemplatePayload = {
  name: string;
  canvas_width: number;
  canvas_height: number;
  background_color: string;
  elements?: CanvasElement[];
};

export type UpdateTemplatePayload = {
  name?: string;
  canvas_width?: number;
  canvas_height?: number;
  background_color?: string;
  elements?: CanvasElement[];
};

export type DuplicateTemplatePayload = {
  new_name: string;
};

export type PreviewTemplatePayload = {
  product_data: Record<string, unknown>;
};

export type PreviewTemplateResponse = {
  template_id: string;
  rendered_elements: CanvasElement[];
};
