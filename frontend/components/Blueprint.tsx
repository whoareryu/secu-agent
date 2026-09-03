export default function Blueprint<T extends React.ElementType = "div">({
  as,
  className = "",
  children,
  ...rest
}: {
  as?: T;
  className?: string;
  children: React.ReactNode;
} & Omit<React.ComponentPropsWithoutRef<T>, "as" | "className" | "children">) {
  const Tag = (as ?? "div") as React.ElementType;
  return (
    <Tag className={`blueprint ${className}`.trim()} {...rest}>
      {children}
    </Tag>
  );
}
