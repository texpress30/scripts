"use client";

const COMMON_FIELDS = [
  { binding: "{{title}}", label: "Product Title", group: "Product" },
  { binding: "{{description}}", label: "Description", group: "Product" },
  { binding: "{{price}}", label: "Price", group: "Product" },
  { binding: "{{sale_price}}", label: "Sale Price", group: "Product" },
  { binding: "{{brand}}", label: "Brand", group: "Product" },
  { binding: "{{image_link}}", label: "Product Image", group: "Media" },
  { binding: "{{additional_image_link}}", label: "Additional Image", group: "Media" },
  { binding: "{{product_type}}", label: "Product Type", group: "Category" },
  { binding: "{{category}}", label: "Category", group: "Category" },
  { binding: "{{availability}}", label: "Availability", group: "Status" },
  { binding: "{{condition}}", label: "Condition", group: "Status" },
  { binding: "{{gtin}}", label: "GTIN/EAN", group: "Identifiers" },
  { binding: "{{mpn}}", label: "MPN", group: "Identifiers" },
  { binding: "{{id}}", label: "Product ID", group: "Identifiers" },
] as const;

interface DynamicFieldPickerProps {
  onSelect: (binding: string) => void;
}

export function DynamicFieldPicker({ onSelect }: DynamicFieldPickerProps) {
  const groups = COMMON_FIELDS.reduce(
    (acc, field) => {
      if (!acc[field.group]) acc[field.group] = [];
      acc[field.group].push(field);
      return acc;
    },
    {} as Record<string, typeof COMMON_FIELDS[number][]>,
  );

  return (
    <div className="w-64 rounded-md border border-slate-200 bg-white shadow-lg dark:border-slate-600 dark:bg-slate-700">
      <div className="border-b border-slate-200 px-3 py-2 dark:border-slate-600">
        <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Insert dynamic field</p>
      </div>
      <div className="max-h-64 overflow-y-auto p-1">
        {Object.entries(groups).map(([group, fields]) => (
          <div key={group}>
            <p className="px-2 pb-1 pt-2 text-xs font-medium text-slate-400 dark:text-slate-500">{group}</p>
            {fields.map((field) => (
              <button
                key={field.binding}
                onClick={() => onSelect(field.binding)}
                className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600"
              >
                <span>{field.label}</span>
                <code className="text-xs text-indigo-500 dark:text-indigo-400">{field.binding}</code>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
