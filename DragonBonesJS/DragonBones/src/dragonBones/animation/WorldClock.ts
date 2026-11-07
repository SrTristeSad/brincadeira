/**
 * The MIT License (MIT)
 *
 * Copyright (c) 2012-2025 DragonBones team and other contributors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
namespace dragonBones {
    /**
     * - Worldclock provides clock support for animations, advance time for each IAnimatable object added to the instance.
     * @see dragonBones.IAnimateble
     * @see dragonBones.Armature
     * @version DragonBones 3.0
     * @language en_US
     */
    /**
     * - WorldClock 对动画提供时钟支持，为每个加入到该实例的 IAnimatable 对象更新时间。
     * @see dragonBones.IAnimateble
     * @see dragonBones.Armature
     * @version DragonBones 3.0
     * @language zh_CN
     */
    export class WorldClock implements IAnimatable {
        /**
         * - Current time. (In seconds)
         * @version DragonBones 3.0
         * @language en_US
         */
        /**
         * - 当前的时间。 (以秒为单位)
         * @version DragonBones 3.0
         * @language zh_CN
         */
        public time: number = 0.0;
        /**
         * - The play speed, used to control animation speed-shift play.
         * [0: Stop play, (0~1): Slow play, 1: Normal play, (1~N): Fast play]
         * @default 1.0
         * @version DragonBones 3.0
         * @language en_US
         */
        /**
         * - 播放速度，用于控制动画变速播放。
         * [0: 停止播放, (0~1): 慢速播放, 1: 正常播放, (1~N): 快速播放]
         * @default 1.0
         * @version DragonBones 3.0
         * @language zh_CN
         */
        public timeScale: number = 1.0;

        private _systemTime: number = 0.0;
        private readonly _animatebles: Array<IAnimatable | null> = [];
        private _clock: WorldClock | null = null;
        // Keep additions and removals safe during nested update callbacks.
        private _advancingDepth: number = 0;
        private _needsCompaction: boolean = false;

        private _compactAnimatables(): void {
            let writeIndex = 0;
            for (let readIndex = 0; readIndex < this._animatebles.length; ++readIndex) {
                const animatable = this._animatebles[readIndex];
                if (animatable !== null) {
                    this._animatebles[writeIndex++] = animatable;
                }
            }

            this._animatebles.length = writeIndex;
            this._needsCompaction = false;
        }

        // Unlink an entry without invoking its clock setter. Also used to
        // roll back registrations when external setters throw or reject them.
        private _removeAnimatableReference(value: IAnimatable): boolean {
            const index = this._animatebles.indexOf(value);
            if (index < 0) {
                return false;
            }

            if (this._advancingDepth > 0) {
                this._animatebles[index] = null;
                this._needsCompaction = true;
            }
            else {
                this._animatebles.splice(index, 1);
            }

            return true;
        }
        /**
         * - Creating a Worldclock instance. Typically, you do not need to create Worldclock instance.
         * When multiple Worldclock instances are running at different speeds, can achieving some specific animation effects, such as bullet time.
         * @version DragonBones 3.0
         * @language en_US
         */
        /**
         * - 创建一个 WorldClock 实例。通常并不需要创建 WorldClock 实例。
         * 当多个 WorldClock 实例使用不同的速度运行时，可以实现一些特殊的动画效果，比如子弹时间等。
         * @version DragonBones 3.0
         * @language zh_CN
         */
        public constructor(time: number = 0.0) {
            this.time = time;
            this._systemTime = new Date().getTime() * 0.001;
        }
        /**
         * - Advance time for all IAnimatable instances.
         * @param passedTime - Passed time. [-1: Automatically calculates the time difference between the current frame and the previous frame, [0~N): Passed time] (In seconds)
         * @version DragonBones 3.0
         * @language en_US
         */
        /**
         * - 为所有的 IAnimatable 实例更新时间。
         * @param passedTime - 前进的时间。 [-1: 自动计算当前帧与上一帧的时间差, [0~N): 前进的时间] (以秒为单位)
         * @version DragonBones 3.0
         * @language zh_CN
         */
        public advanceTime(passedTime: number): void {
            if (passedTime !== passedTime) {
                passedTime = 0.0;
            }

            const currentTime = Date.now() * 0.001;

            if (passedTime < 0.0) {
                passedTime = currentTime - this._systemTime;
            }

            this._systemTime = currentTime;

            if (this.timeScale !== 1.0) {
                passedTime *= this.timeScale;
            }

            if (passedTime === 0.0) {
                return;
            }

            if (passedTime < 0.0) {
                this.time -= passedTime;
            }
            else {
                this.time += passedTime;
            }

            this._advancingDepth++;
            try {
                const length = this._animatebles.length;
                for (let i = 0; i < length; ++i) {
                    const animatable = this._animatebles[i];
                    if (animatable !== null) {
                        animatable.advanceTime(passedTime);
                    }
                }
            }
            finally {
                this._advancingDepth--;
                // Compact only after the outermost update finishes. This prevents
                // reentrant updates from shifting entries under the active loop.
                if (this._advancingDepth === 0 && this._needsCompaction) {
                    this._compactAnimatables();
                }
            }
        }
        /**
         * - Check whether contains a specific instance of IAnimatable.
         * @param value - The IAnimatable instance.
         * @version DragonBones 3.0
         * @language en_US
         */
        /**
         * - 检查是否包含特定的 IAnimatable 实例。
         * @param value - IAnimatable 实例。
         * @version DragonBones 3.0
         * @language zh_CN
         */
        public contains(value: IAnimatable): boolean {
            if (value === this) {
                return false;
            }

            let ancestor: IAnimatable | null = value;
            const visited: Array<IAnimatable> = [];
            while (ancestor !== this && ancestor !== null) {
                // External IAnimatable implementations may expose a corrupt clock
                // cycle. Never let a hierarchy lookup spin forever.
                if (visited.indexOf(ancestor) >= 0) {
                    return false;
                }

                visited.push(ancestor);
                ancestor = ancestor.clock;
            }

            return ancestor === this;
        }
        /**
         * - Add IAnimatable instance.
         * @param value - The IAnimatable instance.
         * @version DragonBones 3.0
         * @language en_US
         */
        /**
         * - 添加 IAnimatable 实例。
         * @param value - IAnimatable 实例。
         * @version DragonBones 3.0
         * @language zh_CN
         */
        public add(value: IAnimatable): void {
            // Reject cycles: they cause infinite recursion during advanceTime().
            if (value === this || (value instanceof WorldClock && value.contains(this))) {
                return;
            }

            if (this._animatebles.indexOf(value) < 0) {
                // A custom IAnimatable may expose clock as a simple field rather
                // than a setter. Detach it explicitly from its previous owner.
                if (value.clock !== null && value.clock !== this) {
                    value.clock.remove(value);
                }

                // Reserve a slot before calling the setter: WorldClock.clock
                // can synchronously call add() on this same owner.
                this._animatebles.push(value);
                let attached = false;
                try {
                    value.clock = this;
                    attached = value.clock === this;
                }
                finally {
                    // An external IAnimatable may throw or reject ownership.
                    // Never advance an entry that does not belong to this clock.
                    if (!attached) {
                        this._removeAnimatableReference(value);
                    }
                }
            }
        }
        /**
         * - Removes a specified IAnimatable instance.
         * @param value - The IAnimatable instance.
         * @version DragonBones 3.0
         * @language en_US
         */
        /**
         * - 移除特定的 IAnimatable 实例。
         * @param value - IAnimatable 实例。
         * @version DragonBones 3.0
         * @language zh_CN
         */
        public remove(value: IAnimatable): void {
            if (this._removeAnimatableReference(value) && value.clock === this) {
                value.clock = null;
            }
        }
        /**
         * - Clear all IAnimatable instances.
         * @version DragonBones 3.0
         * @language en_US
         */
        /**
         * - 清除所有的 IAnimatable 实例。
         * @version DragonBones 3.0
         * @language zh_CN
         */
        public clear(): void {
            // Treat clear as an active traversal. Reentrant clock setters must
            // not shift the indices we are currently visiting.
            this._advancingDepth++;
            try {
                for (let i = 0, l = this._animatebles.length; i < l; ++i) {
                    const animatable = this._animatebles[i];
                    this._animatebles[i] = null;
                    if (animatable !== null) {
                        animatable.clock = null;
                    }
                }
            }
            finally {
                this._advancingDepth--;
                // Discard entries detached by this call, but preserve any new
                // animatables added by a clock setter during the traversal.
                // Also remove holes when a setter throws before clear finishes.
                this._needsCompaction = true;
                if (this._advancingDepth === 0) {
                    this._compactAnimatables();
                }
            }
        }
        /**
         * @inheritDoc
         */
        public get clock(): WorldClock | null {
            return this._clock;
        }
        public set clock(value: WorldClock | null) {
            // A clock cannot be its own ancestor or a descendant of itself.
            if (this._clock === value || value === this || (value !== null && this.contains(value))) {
                return;
            }

            if (this._clock !== null) {
                this._clock.remove(this);
            }

            this._clock = value;

            if (this._clock !== null) {
                this._clock.add(this);
            }
        }
    }
}
