type PagePlaceholderProps = {
  title: string;
  message: string;
};

/** Heading plus a one-line empty state, for pages whose content arrives in later phases. */
export function PagePlaceholder({ title, message }: PagePlaceholderProps) {
  return (
    <section className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
        {title}
      </h1>
      <p className="text-muted-foreground">{message}</p>
    </section>
  );
}
