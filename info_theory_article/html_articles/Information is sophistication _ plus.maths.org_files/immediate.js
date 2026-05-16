/**
 * JS that must run immediately after DOM is ready.
 */
addGutenbergAttributes()

// Alters DOM, such as adding missing attributes that are difficult to add any other way.
function addGutenbergAttributes() {
  // In Gutenberg blocks, adds missing classes
  const colsContainers = document.querySelectorAll('.wp-block-columns')
  // console.debug('colsContainers:', colsContainers)
  colsContainers.forEach((container) => {
    container.setAttribute('data-cols', container.children.length)
  })
}
