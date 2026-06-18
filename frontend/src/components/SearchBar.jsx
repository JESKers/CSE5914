import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

// (1) Search bar — keyword box + submit. Mockup: no live data wired.
export default function SearchBar({ value, onChange, onSearch }) {
  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch?.();
      }}
    >
      <Input
        placeholder="Search by keyword — e.g. luxury coupe, fuel efficient SUV"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
      />
      <Button type="submit">Search</Button>
    </form>
  );
}
