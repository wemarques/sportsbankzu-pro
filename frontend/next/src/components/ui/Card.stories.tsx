import type { Meta, StoryObj } from "@storybook/react";
import { Card, CardHeader, CardContent, CardFooter } from "./card";

const meta: Meta<typeof Card> = {
  title: "UI/Card",
  component: Card,
};
export default meta;
type Story = StoryObj<typeof Card>;

export const Default: Story = {
  render: () => (
    <Card aria-label="Cartão de exemplo">
      <CardHeader>Header</CardHeader>
      <CardContent>Conteúdo</CardContent>
      <CardFooter>Footer</CardFooter>
    </Card>
  ),
};
