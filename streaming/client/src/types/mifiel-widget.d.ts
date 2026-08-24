// TSX intrinsic-element typing for Mifiel's embeddable <mifiel-widget> web
// component (https://app.mifiel.com/widget-component/index.js). Uses the
// global JSX namespace declaration-merge since this project is on React 18 /
// @types/react 18 with "jsx": "react-jsx" (not React 19's JSX.IntrinsicElements
// under the React namespace).
declare namespace JSX {
  interface IntrinsicElements {
    "mifiel-widget": React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        id?: string;
        environment?: "production" | "sandbox";
        "success-btn-text"?: string;
        "container-class"?: string;
      },
      HTMLElement
    >;
  }
}
