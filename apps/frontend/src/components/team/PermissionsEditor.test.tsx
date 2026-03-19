import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PermissionEditorItem, PermissionsEditor } from "./PermissionsEditor";

const items: PermissionEditorItem[] = [
  { key: "dashboard", label: "Dashboard", order: 1, groupKey: "main_nav", groupLabel: "Main Navigation", parentKey: null, isContainer: false },
  { key: "settings", label: "Settings", order: 100, groupKey: "settings", groupLabel: "Settings", parentKey: null, isContainer: true },
  { key: "settings_team", label: "My Team", order: 110, groupKey: "settings", groupLabel: "Settings", parentKey: "settings", isContainer: false },
];

describe("PermissionsEditor", () => {
  it("renders groups, summary and supports toggling", () => {
    const onToggle = vi.fn();
    render(
      <PermissionsEditor
        scope="agency"
        items={items}
        selectedKeys={["dashboard", "settings", "settings_team"]}
        onToggle={onToggle}
        summaryHint="hint"
      />,
    );

    expect(screen.getByText(/3 \/ 3 active/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Main Navigation/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Settings/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Dashboard" }));
    expect(onToggle).toHaveBeenCalledWith("dashboard");
  });

  it("filters by search on label/key/group", () => {
    render(
      <PermissionsEditor
        scope="subaccount"
        items={items}
        selectedKeys={[]}
        onToggle={() => {}}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Caută după label, key sau grup"), { target: { value: "team" } });
    fireEvent.click(screen.getByRole("button", { name: /Settings/i }));
    expect(screen.getByText("My Team")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
  });

  it("shows disabled reason for non-grantable entries", () => {
    render(
      <PermissionsEditor
        scope="subaccount"
        items={[{ ...items[0], disabledReason: "Nu poate fi acordat" }]}
        selectedKeys={[]}
        onToggle={() => {}}
        getItemDisabled={() => true}
      />,
    );

    expect(screen.getByText("Nu poate fi acordat")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Dashboard/ })).toBeDisabled();
  });
});
