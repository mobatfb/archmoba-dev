import java.awt.Color;
import java.awt.GradientPaint;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.RadialGradientPaint;
import java.awt.geom.Point2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.util.ArrayDeque;
import javax.imageio.ImageIO;

/**
 * Genera un icono PNG CUADRADO sin modificar el logo usado en el splash.
 * JDK 17, sin dependencias. Uso:
 * java GenerateIcon.java origen.png destino.png
 */
public final class GenerateIcon {
    private static final int SIZE = 512;
    private static final int BLACK_EDGE_LIMIT = 46;

    private GenerateIcon() {}

    private static int brightness(int pixel) {
        return Math.max((pixel >>> 16) & 255,
                Math.max((pixel >>> 8) & 255, pixel & 255));
    }

    /** Solo hace transparente el negro externo conectado a los bordes. */
    private static BufferedImage removeExternalBlack(BufferedImage source) {
        int width = source.getWidth();
        int height = source.getHeight();
        int count = width * height;
        int[] pixels = source.getRGB(0, 0, width, height, null, 0, width);
        boolean[] external = new boolean[count];
        ArrayDeque<Integer> queue = new ArrayDeque<>();
        for (int x = 0; x < width; x++) {
            push(x, pixels, external, queue);
            push((height - 1) * width + x, pixels, external, queue);
        }
        for (int y = 0; y < height; y++) {
            push(y * width, pixels, external, queue);
            push(y * width + width - 1, pixels, external, queue);
        }
        while (!queue.isEmpty()) {
            int index = queue.removeFirst();
            int x = index % width, y = index / width;
            if (x > 0) push(index - 1, pixels, external, queue);
            if (x + 1 < width) push(index + 1, pixels, external, queue);
            if (y > 0) push(index - width, pixels, external, queue);
            if (y + 1 < height) push(index + width, pixels, external, queue);
        }
        for (int i = 0; i < count; i++) {
            if (!external[i]) continue;
            int level = brightness(pixels[i]);
            int alpha = Math.max(0, Math.min(255, (level - 9) * 255 / 38));
            int previous = (pixels[i] >>> 24) & 255;
            pixels[i] = ((alpha * previous / 255) << 24) | (pixels[i] & 0x00ffffff);
        }
        BufferedImage result = new BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB);
        result.setRGB(0, 0, width, height, pixels, 0, width);
        return result;
    }

    private static void push(int index, int[] pixels, boolean[] external,
                             ArrayDeque<Integer> queue) {
        if (!external[index] && brightness(pixels[index]) <= BLACK_EDGE_LIMIT) {
            external[index] = true;
            queue.addLast(index);
        }
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 2) {
            throw new IllegalArgumentException("Uso: GenerateIcon origen.png destino.png");
        }
        BufferedImage source = ImageIO.read(new File(args[0]));
        if (source == null) throw new IOException("No es una imagen PNG valida.");
        BufferedImage logo = removeExternalBlack(source);
        BufferedImage square = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = square.createGraphics();
        try {
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,
                    RenderingHints.VALUE_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                    RenderingHints.VALUE_INTERPOLATION_BICUBIC);
            g.setRenderingHint(RenderingHints.KEY_RENDERING,
                    RenderingHints.VALUE_RENDER_QUALITY);
            // Lienzo CUADRADO sin transparencia; Android recorta la mascara.
            g.setPaint(new GradientPaint(0, 0, new Color(2, 10, 24),
                    SIZE, SIZE, new Color(0, 1, 8)));
            g.fillRect(0, 0, SIZE, SIZE);
            g.setPaint(new RadialGradientPaint(
                    new Point2D.Float(185, 320), 380f,
                    new float[]{0f, 0.5f, 1f},
                    new Color[]{new Color(0, 73, 142, 120),
                            new Color(0, 39, 85, 55), new Color(0, 0, 0, 0)}));
            g.fillRect(0, 0, SIZE, SIZE);
            // Imagen ORIGINAL conservando proporcion 348:232 y sin marcos.
            int displayWidth = 492;
            int displayHeight = Math.round(
                    displayWidth * (float) logo.getHeight() / logo.getWidth());
            if (displayHeight > 470) {
                displayHeight = 470;
                displayWidth = Math.round(
                        displayHeight * (float) logo.getWidth() / logo.getHeight());
            }
            g.drawImage(logo, (SIZE - displayWidth) / 2,
                    (SIZE - displayHeight) / 2, displayWidth, displayHeight, null);
        } finally {
            g.dispose();
        }
        File output = new File(args[1]);
        File folder = output.getParentFile();
        if (folder != null && !folder.isDirectory() && !folder.mkdirs()) {
            throw new IOException("No se pudo crear carpeta de recursos Android.");
        }
        if (!ImageIO.write(square, "png", output)) {
            throw new IOException("No se pudo escribir el icono PNG.");
        }
        BufferedImage verified = ImageIO.read(output);
        if (verified.getWidth() != SIZE || verified.getHeight() != SIZE) {
            throw new IOException("El icono generado no tiene formato cuadrado.");
        }
        System.out.println("Icono cuadrado de 512x512 creado: " + output.getPath());
    }
}
