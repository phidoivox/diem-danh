import { useEffect, useState } from "react";

/**
 * Debounce 1 giá trị (ô tìm kiếm server-side): trả bản sao chậm `delay`ms.
 * Gõ live không nút Tìm, queryKey chỉ đổi khi người dùng dừng tay.
 */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}
