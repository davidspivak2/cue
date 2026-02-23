import * as React from "react";

export const useWindowHeight = () => {
  const [height, setHeight] = React.useState(() => window.innerHeight);

  React.useEffect(() => {
    const handleResize = () => setHeight(window.innerHeight);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return height;
};
