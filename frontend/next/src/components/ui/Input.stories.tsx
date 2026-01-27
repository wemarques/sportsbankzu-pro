import type { Meta, StoryObj } from "@storybook/react";
import { Input } from "./input";

const meta: Meta<typeof Input> = {
  title: "UI/Input",
  component: Input,
  args: { placeholder: "Digite aqui" },
};
export default meta;
type Story = StoryObj<typeof Input>;

export const Default: Story = {};
export const WithAria: Story = { args: { "aria-label": "Campo de texto" } };
