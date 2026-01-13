const sharp = require('sharp');
const pngToIco = require('png-to-ico').default || require('png-to-ico');
const fs = require('fs');
const path = require('path');

async function generate() {
    const svgPath = path.join(__dirname, '../assets/logo.svg');
    const pngPath = path.join(__dirname, '../assets/logo.png');
    const icoPath = path.join(__dirname, '../assets/favicon.ico');

    console.log('Generating logo.png...');
    await sharp(svgPath)
        .resize(512, 512)
        .png()
        .toFile(pngPath);
    console.log('logo.png generated.');

    console.log('Generating favicon.ico...');
    try {
        const buf = await pngToIco(pngPath);
        fs.writeFileSync(icoPath, buf);
        console.log('favicon.ico generated.');
    } catch (e) {
        console.error('Error generating ICO:', e);
    }
}

generate();
