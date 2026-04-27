export function focusFirstOverlayItemInViewport({
  overlayItems,
  pageImages,
  pageImageSizes,
  pageElementRefs,
  viewportElement,
  viewportWidth,
  zoom,
}) {
  if (!Array.isArray(overlayItems) || !overlayItems.length || !viewportElement) {
    return;
  }

  const pageOrder = new Map((pageImages || []).map((page, index) => [page.id, index]));
  const rankedItems = [...overlayItems]
    .filter((item) => item?.page_id && item?.bbox)
    .sort((left, right) => {
      const leftPage = pageOrder.get(left.page_id) ?? Number.MAX_SAFE_INTEGER;
      const rightPage = pageOrder.get(right.page_id) ?? Number.MAX_SAFE_INTEGER;
      if (leftPage !== rightPage) {
        return leftPage - rightPage;
      }

      const [leftL = 0, leftT = 0] = String(left.bbox)
        .split(",")
        .map((part) => Number.parseFloat(part));
      const [rightL = 0, rightT = 0] = String(right.bbox)
        .split(",")
        .map((part) => Number.parseFloat(part));

      if (leftT !== rightT) {
        return leftT - rightT;
      }
      return leftL - rightL;
    });

  const targetItem = rankedItems[0];
  if (!targetItem) {
    return;
  }

  const pageElement = pageElementRefs.current?.[targetItem.page_id];
  if (!(pageElement instanceof HTMLElement)) {
    return;
  }

  const [left, top, right, bottom] = String(targetItem.bbox)
    .split(",")
    .map((part) => Number.parseFloat(part));
  if (![left, top, right, bottom].every(Number.isFinite)) {
    return;
  }

  const imageWidth =
    Number(targetItem.image_width || pageImageSizes?.[targetItem.page_id]?.width || 0);
  const imageHeight =
    Number(targetItem.image_height || pageImageSizes?.[targetItem.page_id]?.height || 0);
  if (!(imageWidth > 0) || !(imageHeight > 0)) {
    return;
  }

  const imageElement = pageElement.querySelector("img");
  if (!(imageElement instanceof HTMLImageElement)) {
    return;
  }

  const displayWidth = imageElement.clientWidth;
  const displayHeight = imageElement.clientHeight;
  if (!(displayWidth > 0) || !(displayHeight > 0)) {
    return;
  }

  const centerX = ((left + right) / 2 / imageWidth) * displayWidth;
  const centerY = ((top + bottom) / 2 / imageHeight) * displayHeight;
  const viewportRect = viewportElement.getBoundingClientRect();
  const imageRect = imageElement.getBoundingClientRect();

  const centerXInContent =
    viewportElement.scrollLeft + (imageRect.left - viewportRect.left) + centerX;
  const centerYInContent =
    viewportElement.scrollTop + (imageRect.top - viewportRect.top) + centerY;

  const targetScrollLeft = Math.max(0, centerXInContent - viewportElement.clientWidth / 2);
  const targetScrollTop = Math.max(0, centerYInContent - viewportElement.clientHeight / 2);

  viewportElement.scrollTo({
    left: targetScrollLeft,
    top: targetScrollTop,
    behavior: "smooth",
  });
}
