/*
 * Javascript for commonly needed utilities
 * for loading images via a proxy.
 */
var DISABLE_IMAGE_PROXY = false;

function imgLoaded(imgElement) {
	return imgElement.complete && imgElement.naturalHeight !== 0;
}

function wait(ms){
	var start = new Date().getTime();
	var end = start;
	while(end < start + ms) {
	  end = new Date().getTime();
   }
}

var images = document.images;
function proxyLoadMerrittImages(attempt) {
	// Checks to see if images load, if not
	var proxy_param = "?merritt-proxy=";
	var proxy_start = base_url + "/entities/proxy/";
	var waiting_gif = base_url + "/static/oc/images/ui/waiting.gif";
	var merritt_start = "https://merritt.cdlib.org";

	if (DISABLE_IMAGE_PROXY == true || attempt >= 2){
		// Skip. Do not look for images.
		return true;
	}
	else{
		images = document.images;
	}

	for (var i=0; i < images.length; i++) {
		var image = images[i];
		var src = image.src;
		if (!image.getAttribute("orig_src")) {
			image.orig_src = image.src;
			image.setAttribute("orig_src", src);
		}
		if (!imgLoaded(image) && (
			image.orig_src.startsWith(merritt_start))){
			image.setAttribute("src", src);		
		}
	}
	var proxy_count = 0;
	for (var i=0; i < images.length; i++) {
		var image = images[i];
		var orig_src = image.orig_src;
		if ((!imgLoaded(image) || image.src == waiting_gif) && (
			orig_src.startsWith(merritt_start) && proxy_count < 2)){
			// Use the orig_src to set the image src.
			// Via a proxy fetch. This will get the Merritt
			// image if we don't already have it.
			proxy_count += 1;
			src = proxy_start + encodeURI(orig_src);
			image.setAttribute("src", src);
			console.log('Image now: ' + image.src);
		}
	}
}
